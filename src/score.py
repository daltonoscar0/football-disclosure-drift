"""Stage 4: year-over-year disclosure drift on strategic reports.

Two novelty scores per consecutive year pair, both in the spirit of Lazy Prices
(Cohen, Malloy & Nguyen): what matters is *change* in language between consecutive
filings, not absolute complexity of either one.

  similarity drop   TF-IDF cosine and raw Jaccard between year t and year t-1.
                    novelty = 1 - similarity. The TF-IDF vocabulary and document
                    frequencies are fit per club, over that club's own documents
                    only, so a club's boilerplate is discounted against itself.

  surprisal         mean per-token negative log2 probability of year t's report
                    under an interpolated Kneser-Ney n-gram model fit on year t-1's
                    report. Higher = year t reads as more unexpected given last
                    year's language.

Both are implemented in stdlib. Everything iterates in sorted order and contains no
randomness, so repeated runs are byte-identical.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .util import ROOT, has_parsed_filings, jdump, jload

PARSED = ROOT / "data" / "parsed"
SCORES = ROOT / "data" / "scores"
DRIFT_CSV = SCORES / "drift.csv"
RANKING_CSV = SCORES / "ranking.csv"
SANITY_JSON = SCORES / "sanity.json"

NGRAM_ORDER = 3
KN_DISCOUNT = 0.75
MIN_TOKENS = 200

TOKEN_RE = re.compile(r"[a-z][a-z'’-]*")
# Digits and currency figures are stripped: every filing restates last year's
# numbers, so leaving them in would score routine numeric updates as language drift.
NUMBER_RE = re.compile(r"[£$€]?\d[\d,.]*%?")


def tokenize(text: str) -> list[str]:
    text = NUMBER_RE.sub(" ", text.lower())
    return TOKEN_RE.findall(text)


# -- similarity ------------------------------------------------------------


def tf_idf_vectors(docs: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    """Sublinear TF times smoothed IDF, L2-normalised, fit over `docs` only."""
    n_docs = len(docs)
    df: Counter[str] = Counter()
    for tokens in docs.values():
        df.update(set(tokens))
    vectors: dict[str, dict[str, float]] = {}
    for key in sorted(docs):
        counts = Counter(docs[key])
        vec: dict[str, float] = {}
        for term in sorted(counts):
            tf = 1.0 + math.log(counts[term])
            idf = math.log((1.0 + n_docs) / (1.0 + df[term])) + 1.0
            vec[term] = tf * idf
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors[key] = {t: v / norm for t, v in vec.items()}
    return vectors


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(t, 0.0) for t, w in a.items())


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


# -- Kneish-Ney surprisal --------------------------------------------------


class KNModel:
    """Interpolated Kneser-Ney over orders 1..n, fit on a single document.

    Standard recursive formulation. The highest order uses raw n-gram counts; every
    lower order uses *continuation* counts — how many distinct words precede a gram,
    rather than how often it occurs — which is what stops KN from over-predicting
    frequent-but-context-bound words. Order 1 backs off to a uniform distribution
    over the vocabulary plus one slot for out-of-vocabulary tokens.

    Per order k we keep three tables:
      num[k][gram]    numerator count (raw at k = n, continuation below)
      den[k][context] sum of num[k] over all continuations of that context
      fol[k][context] number of distinct continuations with non-zero num
    """

    def __init__(self, tokens: list[str], order: int = NGRAM_ORDER, discount: float = KN_DISCOUNT):
        self.order = order
        self.d = discount
        pad = ["<s>"] * (order - 1)
        seq = pad + tokens + ["</s>"]

        raw: list[Counter] = [Counter() for _ in range(order + 2)]
        for k in range(1, order + 1):
            for i in range(len(seq) - k + 1):
                raw[k][tuple(seq[i : i + k])] += 1

        self.num: list[Counter] = [Counter() for _ in range(order + 1)]
        self.num[order] = raw[order]
        for k in range(1, order):
            continuation: Counter = Counter()
            for gram in raw[k + 1]:
                continuation[gram[1:]] += 1
            self.num[k] = continuation

        self.den: list[Counter] = [Counter() for _ in range(order + 1)]
        self.fol: list[Counter] = [Counter() for _ in range(order + 1)]
        for k in range(1, order + 1):
            for gram, count in self.num[k].items():
                context = gram[:-1]
                self.den[k][context] += count
                if count:
                    self.fol[k][context] += 1

        self.vocab = set(tokens) | {"</s>"}
        self.v_size = len(self.vocab) + 1  # +1 for OOV

    def _prob(self, gram: tuple[str, ...], k: int) -> float:
        context = gram[:-1]
        den = self.den[k].get(context, 0)
        lower = 1.0 / self.v_size if k == 1 else self._prob(gram[1:], k - 1)
        if not den:
            return lower
        lam = self.d * self.fol[k].get(context, 0) / den
        higher = max(self.num[k].get(gram, 0) - self.d, 0.0) / den
        return higher + lam * lower

    def surprisal(self, tokens: list[str]) -> float:
        """Mean per-token surprisal in bits."""
        pad = ["<s>"] * (self.order - 1)
        seq = pad + tokens + ["</s>"]
        total = 0.0
        n = 0
        floor = 1.0 / (self.v_size * 64)
        for i in range(self.order - 1, len(seq)):
            gram = tuple(seq[i - self.order + 1 : i + 1])
            p = max(self._prob(gram, self.order), floor)
            total += -math.log2(p)
            n += 1
        return total / n if n else 0.0


# -- pipeline --------------------------------------------------------------


def load_strategic_reports() -> tuple[dict[str, dict[str, str]], list[dict]]:
    """{club: {year: strategic report text}}, excluding flagged-unusable filings."""
    docs: dict[str, dict[str, str]] = defaultdict(dict)
    excluded: list[dict] = []
    for club_dir in sorted(p for p in PARSED.iterdir() if p.is_dir()):
        for path in sorted(club_dir.glob("*.json")):
            d = jload(path)
            text = d["sections"].get("strategic_report", "")
            blocking = [
                f
                for f in d["flags"]
                if f in ("empty_text_layer", "suspect_text_layer", "short_strategic_report")
            ]
            if blocking or len(tokenize(text)) < MIN_TOKENS:
                excluded.append(
                    {"club": d["club"], "year": d["year"], "reason": blocking or ["too_few_tokens"]}
                )
                continue
            docs[d["club"]][d["year"]] = text
    if excluded:
        for e in excluded:
            print(
                f"excluding {e['club']} {e['year']}: {','.join(e['reason'])}",
                file=sys.stderr,
            )
    return dict(docs), excluded


def score_club(years: dict[str, str]) -> list[dict]:
    tokens = {y: tokenize(t) for y, t in sorted(years.items())}
    vectors = tf_idf_vectors(tokens)
    ordered = sorted(tokens)
    rows = []
    for prev, curr in zip(ordered, ordered[1:]):
        cos = cosine(vectors[prev], vectors[curr])
        jac = jaccard(tokens[prev], tokens[curr])
        model = KNModel(tokens[prev])
        rows.append(
            {
                "year_prev": prev,
                "year": curr,
                "n_tokens_prev": len(tokens[prev]),
                "n_tokens": len(tokens[curr]),
                "cosine_similarity": round(cos, 6),
                "cosine_novelty": round(1.0 - cos, 6),
                "jaccard_similarity": round(jac, 6),
                "jaccard_novelty": round(1.0 - jac, 6),
                "surprisal_bits": round(model.surprisal(tokens[curr]), 6),
            }
        )
    return rows


def sanity_checks(docs: dict[str, dict[str, str]]) -> dict:
    """Identical documents must score ~0 novelty; shuffled text must score high."""
    club = sorted(docs)[0]
    year = sorted(docs[club])[-1]
    tokens = tokenize(docs[club][year])

    vecs = tf_idf_vectors({"a": tokens, "b": list(tokens)})
    identical_cos_novelty = 1.0 - cosine(vecs["a"], vecs["b"])
    identical_jac_novelty = 1.0 - jaccard(tokens, list(tokens))
    identical_surprisal = KNModel(tokens).surprisal(tokens)

    # Deterministic shuffle: a fixed stride permutation, no RNG involved.
    stride = 7
    shuffled = [tokens[(i * stride) % len(tokens)] for i in range(len(tokens))]
    shuffled_surprisal = KNModel(tokens).surprisal(shuffled)

    return {
        "reference": {"club": club, "year": year, "n_tokens": len(tokens)},
        "identical_cosine_novelty": round(identical_cos_novelty, 9),
        "identical_jaccard_novelty": round(identical_jac_novelty, 9),
        "identical_surprisal_bits": round(identical_surprisal, 6),
        "shuffled_surprisal_bits": round(shuffled_surprisal, 6),
        "passes": {
            "identical_cosine_novelty_near_zero": identical_cos_novelty < 1e-9,
            "identical_jaccard_novelty_zero": identical_jac_novelty < 1e-12,
            "shuffled_more_surprising_than_identical": shuffled_surprisal
            > identical_surprisal,
        },
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run() -> int:
    if not has_parsed_filings(PARSED):
        print("error: nothing parsed yet — run `make parse` first.", file=sys.stderr)
        return 1
    docs, excluded = load_strategic_reports()
    if not docs:
        print("error: no usable strategic reports.", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for club in sorted(docs):
        for row in score_club(docs[club]):
            rows.append({"club": club, **row})

    fields = [
        "club",
        "year_prev",
        "year",
        "n_tokens_prev",
        "n_tokens",
        "cosine_similarity",
        "cosine_novelty",
        "jaccard_similarity",
        "jaccard_novelty",
        "surprisal_bits",
    ]
    write_csv(DRIFT_CSV, rows, fields)

    ranking = []
    for club in sorted(docs):
        club_rows = [r for r in rows if r["club"] == club]
        if not club_rows:
            continue
        ranking.append(
            {
                "club": club,
                "n_pairs": len(club_rows),
                "mean_cosine_novelty": round(
                    sum(r["cosine_novelty"] for r in club_rows) / len(club_rows), 6
                ),
                "max_cosine_novelty": round(
                    max(r["cosine_novelty"] for r in club_rows), 6
                ),
                "mean_jaccard_novelty": round(
                    sum(r["jaccard_novelty"] for r in club_rows) / len(club_rows), 6
                ),
                "mean_surprisal_bits": round(
                    sum(r["surprisal_bits"] for r in club_rows) / len(club_rows), 6
                ),
                "max_surprisal_bits": round(
                    max(r["surprisal_bits"] for r in club_rows), 6
                ),
            }
        )
    ranking.sort(key=lambda r: (-r["mean_cosine_novelty"], r["club"]))
    write_csv(
        RANKING_CSV,
        ranking,
        [
            "club",
            "n_pairs",
            "mean_cosine_novelty",
            "max_cosine_novelty",
            "mean_jaccard_novelty",
            "mean_surprisal_bits",
            "max_surprisal_bits",
        ],
    )

    checks = sanity_checks(docs)
    checks["excluded_filings"] = excluded
    jdump(checks, SANITY_JSON)

    for row in rows:
        print(
            f"{row['club']:<11}{row['year_prev']}->{row['year']}  "
            f"cos_nov={row['cosine_novelty']:.4f}  "
            f"jac_nov={row['jaccard_novelty']:.4f}  "
            f"surprisal={row['surprisal_bits']:.3f} bits"
        )
    failed = [k for k, v in checks["passes"].items() if not v]
    print(f"\nsanity checks: {'all pass' if not failed else 'FAILED ' + ','.join(failed)}")
    print(f"wrote {DRIFT_CSV.relative_to(ROOT)} and {RANKING_CSV.relative_to(ROOT)}")
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
