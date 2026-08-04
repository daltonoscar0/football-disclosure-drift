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
