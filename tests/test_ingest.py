from src.ingest import CLUBS, _accounts_summary, _pick_filings, _plausible, _year_of


def _filing(date, description="accounts-with-accounts-type-group", made_up=None, txn="t"):
    return {
        "type": "AA",
        "date": date,
        "description": description,
        "transaction_id": txn,
        "description_values": {"made_up_date": made_up or date},
        "links": {"document_metadata": f"https://x/document/{txn}"},
    }


class FakeClient:
    def __init__(self, filings):
        self._filings = filings

    def filing_history(self, company_number, **kwargs):
        return list(self._filings)


def test_group_accounts_rank_above_small_accounts():
    group = _accounts_summary([_filing("2024-03-01")])
    small = _accounts_summary([_filing("2024-03-01", "accounts-with-accounts-type-small")])
    assert group["best_rank"] < small["best_rank"]
    assert group["n_usable_recent"] == 1
    assert small["n_usable_recent"] == 0


def test_dissolved_and_supporters_club_candidates_are_rejected():
    chelsea = CLUBS[0]
    assert _plausible({"title": "CHELSEA FC PLC", "company_status": "active"}, chelsea)
    assert not _plausible(
        {"title": "CHELSEA SUPPORTERS TRUST", "company_status": "active"}, chelsea
    )
    assert not _plausible(
        {"title": "CHELSEA FC HOLDINGS LIMITED", "company_status": "dissolved"}, chelsea
    )


def test_picks_three_most_recent_distinct_periods():
    filings = [
        _filing("2024-03-01", made_up="2023-06-30", txn="a"),
        _filing("2023-03-01", made_up="2022-06-30", txn="b"),
        _filing("2022-03-01", made_up="2021-06-30", txn="c"),
        _filing("2021-03-01", made_up="2020-06-30", txn="d"),
    ]
    picked = _pick_filings(FakeClient(filings), "0000")
    assert [f["transaction_id"] for f in picked] == ["a", "b", "c"]


def test_amended_accounts_do_not_crowd_out_an_earlier_year():
    filings = [
        _filing("2024-09-01", made_up="2023-06-30", txn="amended"),
        _filing("2024-03-01", made_up="2023-06-30", txn="original"),
        _filing("2023-03-01", made_up="2022-06-30", txn="prior"),
    ]
    picked = _pick_filings(FakeClient(filings), "0000")
    assert [f["transaction_id"] for f in picked] == ["amended", "prior"]


def test_small_accounts_are_not_downloaded():
    filings = [_filing("2024-03-01", "accounts-with-accounts-type-small")]
    assert _pick_filings(FakeClient(filings), "0000") == []


def test_year_comes_from_the_made_up_date_not_the_filing_date():
    assert _year_of(_filing("2024-03-01", made_up="2023-06-30")) == "2023"


def test_substring_lookalikes_are_rejected():
    """Loose substring matching pulled in unrelated companies; whole-word or
    full-phrase matching is required."""
    chelsea, west_ham = CLUBS[0], CLUBS[3]
    assert not _plausible({"title": "AGE UK KENSINGTON AND CHELSEA", "company_status": "active"}, chelsea)
    assert not _plausible({"title": "THE BLUECOAT", "company_status": "active"}, chelsea)
    assert not _plausible({"title": "BESTWAY WHOLESALE HOLDINGS LIMITED", "company_status": "active"}, west_ham)
    assert not _plausible({"title": "AMEC FOSTER WHEELER (HOLDINGS) LIMITED", "company_status": "active"}, west_ham)


def test_genuine_entities_survive_the_filter():
    chelsea, arsenal, west_ham = CLUBS[0], CLUBS[1], CLUBS[3]
    assert _plausible({"title": "CHELSEA FC HOLDINGS LIMITED", "company_status": "active"}, chelsea)
    assert _plausible({"title": "FORDSTAM LIMITED", "company_status": "active"}, chelsea)
    assert _plausible({"title": "BLUECO 22 LIMITED", "company_status": "active"}, chelsea)
    # A leading "The" must not hide the club name.
    assert _plausible({"title": "THE ARSENAL FOOTBALL CLUB LIMITED", "company_status": "active"}, arsenal)
    assert _plausible({"title": "WH HOLDING LIMITED", "company_status": "active"}, west_ham)


def test_fully_cached_requires_every_club_and_filing(tmp_path, monkeypatch):
    """A complete cache must not demand an API key; a partial one must."""
    import json

    from src import ingest

    entities = tmp_path / "entities.json"
    manifest = tmp_path / "manifest.json"
    raw = tmp_path / "raw"
    monkeypatch.setattr(ingest, "ENTITIES_PATH", entities)
    monkeypatch.setattr(ingest, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(ingest, "ROOT", tmp_path)

    assert ingest.fully_cached() is False  # nothing on disk

    slugs = [c["slug"] for c in ingest.CLUBS]
    entities.write_text(json.dumps({"clubs": {s: {"chosen": "0001"} for s in slugs}}))

    filings = []
    for slug in slugs:
        for year in ("2023", "2024", "2025"):
            rel = f"raw/{slug}/{year}.pdf"
            (raw / slug).mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_bytes(b"%PDF-1.4 stub")
            filings.append({"club": slug, "year": year, "path": rel})
    manifest.write_text(json.dumps({"filings": filings}))
    assert ingest.fully_cached() is True

    # One filing missing from disk is enough to require a fetch.
    (tmp_path / filings[0]["path"]).unlink()
    assert ingest.fully_cached() is False


def test_unresolved_club_is_not_treated_as_cached(tmp_path, monkeypatch):
    import json

    from src import ingest

    entities = tmp_path / "entities.json"
    monkeypatch.setattr(ingest, "ENTITIES_PATH", entities)
    monkeypatch.setattr(ingest, "MANIFEST_PATH", tmp_path / "manifest.json")
    slugs = [c["slug"] for c in ingest.CLUBS]
    clubs = {s: {"chosen": "0001"} for s in slugs}
    clubs[slugs[0]]["chosen"] = None
    entities.write_text(json.dumps({"clubs": clubs}))
    (tmp_path / "manifest.json").write_text(json.dumps({"filings": []}))
    assert ingest.fully_cached() is False
