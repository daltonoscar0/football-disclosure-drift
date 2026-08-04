from src.score import KNModel, cosine, jaccard, score_club, tf_idf_vectors, tokenize

PROSE_A = (
    "The group delivered turnover growth driven by broadcast and commercial income "
    "and the board continues to invest in the stadium and the academy. Wages "
    "remained the largest single cost and the directors monitor the ratio closely. "
) * 12
PROSE_B = (
    "The group completed the disposal of the hotels and the women's team to a fellow "
    "group company. The profit on disposal is presented within operating profit. "
    "Revenue was broadly flat and the directors note continued cost discipline. "
) * 12


def test_tokenize_strips_figures():
    tokens = tokenize("Turnover of £468,712 rose 12% to a record level in 2024.")
    assert "468" not in tokens and "2024" not in tokens
    assert tokens[:2] == ["turnover", "of"]


def test_identical_documents_have_zero_novelty():
    tokens = tokenize(PROSE_A)
    vectors = tf_idf_vectors({"a": tokens, "b": list(tokens)})
    assert 1.0 - cosine(vectors["a"], vectors["b"]) < 1e-9
    assert 1.0 - jaccard(tokens, list(tokens)) == 0.0


def test_different_documents_have_high_novelty():
    a, b = tokenize(PROSE_A), tokenize(PROSE_B)
    vectors = tf_idf_vectors({"a": a, "b": b})
    assert 1.0 - cosine(vectors["a"], vectors["b"]) > 0.3
    assert 1.0 - jaccard(a, b) > 0.3


def test_self_surprisal_is_low_and_cross_surprisal_is_high():
    a, b = tokenize(PROSE_A), tokenize(PROSE_B)
    model = KNModel(a)
    assert model.surprisal(a) < model.surprisal(b)


def test_shuffled_text_is_more_surprising_than_the_original():
    a = tokenize(PROSE_A)
    model = KNModel(a)
    shuffled = [a[(i * 7) % len(a)] for i in range(len(a))]
    assert model.surprisal(shuffled) > model.surprisal(a)


def test_language_model_is_a_proper_distribution():
    """Probabilities over the vocabulary for a fixed context must not exceed 1."""
    tokens = tokenize(PROSE_A)
    model = KNModel(tokens)
    context = ("the", "group")
    total = sum(model._prob(context + (w,), model.order) for w in sorted(model.vocab))
    assert 0.9 < total <= 1.0


def test_scoring_is_deterministic():
    years = {"2022": PROSE_A, "2023": PROSE_B, "2024": PROSE_A + PROSE_B}
    first = score_club(years)
    second = score_club(dict(reversed(list(years.items()))))
    assert first == second


def test_score_club_emits_consecutive_pairs_in_order():
    rows = score_club({"2022": PROSE_A, "2023": PROSE_B, "2024": PROSE_A})
    assert [(r["year_prev"], r["year"]) for r in rows] == [
        ("2022", "2023"),
        ("2023", "2024"),
    ]
    for row in rows:
        assert 0.0 <= row["cosine_novelty"] <= 1.0
        assert 0.0 <= row["jaccard_novelty"] <= 1.0
        assert row["surprisal_bits"] > 0.0
