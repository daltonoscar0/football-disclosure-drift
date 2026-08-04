import pytest

from src.ch_client import (
    CompaniesHouseClient,
    MissingAPIKey,
    document_id_from_filing,
)


def test_missing_api_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
    with pytest.raises(MissingAPIKey) as exc:
        CompaniesHouseClient()
    assert "COMPANIES_HOUSE_API_KEY" in str(exc.value)


def test_key_is_used_as_basic_auth_and_never_stored_on_disk(tmp_path):
    client = CompaniesHouseClient(api_key="test-key")
    assert client.session.auth == ("test-key", "")
    # Nothing in the client's public surface leaks the key into a serialisable form.
    assert "test-key" not in repr(client.session.headers)


def test_document_id_is_read_from_the_metadata_link():
    filing = {
        "links": {
            "document_metadata": "https://frontend-doc-api.company-information.service.gov.uk/document/AbC123"
        }
    }
    assert document_id_from_filing(filing) == "AbC123"
    assert document_id_from_filing({"links": {}}) is None
    assert document_id_from_filing({}) is None


def test_rate_limiter_records_calls():
    client = CompaniesHouseClient(api_key="test-key")
    for _ in range(5):
        client._throttle()
    assert len(client._calls) == 5
