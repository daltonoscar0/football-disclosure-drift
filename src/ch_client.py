"""Companies House API wrapper.

Covers the three endpoints Ledger needs: company search, filing history, and
document download. The API key is read from COMPANIES_HOUSE_API_KEY and used as
HTTP Basic auth username with an empty password, which is what Companies House
expects.

Rate limit is 600 requests per 5 minutes. We keep a rolling window of request
timestamps and sleep until the oldest one ages out rather than trusting a fixed
delay, plus exponential backoff on 429 and 5xx.
"""

from __future__ import annotations

import collections
import os
import random
import time

import requests

REST_BASE = "https://api.company-information.service.gov.uk"
DOC_BASE = "https://document-api.company-information.service.gov.uk"

RATE_LIMIT = 600
RATE_WINDOW = 300.0
MAX_RETRIES = 5


class CompaniesHouseError(RuntimeError):
    pass


class MissingAPIKey(CompaniesHouseError):
    pass


class CompaniesHouseClient:
    def __init__(self, api_key: str | None = None, timeout: float = 60.0) -> None:
        key = api_key if api_key is not None else os.environ.get("COMPANIES_HOUSE_API_KEY")
        if not key:
            raise MissingAPIKey(
                "COMPANIES_HOUSE_API_KEY is not set. Export it before running the "
                "ingest stage; it is never written to disk."
            )
        self._key = key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (key, "")
        self.session.headers["User-Agent"] = "ledger-research/0.1"
        self._calls: collections.deque[float] = collections.deque()

    # -- rate limiting ----------------------------------------------------

    def _throttle(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] > RATE_WINDOW:
            self._calls.popleft()
        if len(self._calls) >= RATE_LIMIT:
            sleep_for = RATE_WINDOW - (now - self._calls[0]) + 0.5
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._throttle()
            return
        self._calls.append(now)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:  # network flake
                last_error = exc
                time.sleep(_backoff(attempt))
                continue

            if resp.status_code == 401:
                raise CompaniesHouseError(
                    "Companies House returned 401 Unauthorized. The API key is "
                    "present but rejected — check it is a REST API key (not a "
                    "streaming key) and that it is active."
                )
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 0) or 0)
                time.sleep(max(retry_after, _backoff(attempt)))
                continue
            if resp.status_code >= 500:
                last_error = CompaniesHouseError(f"{resp.status_code} from {url}")
                time.sleep(_backoff(attempt))
                continue
            return resp

        raise CompaniesHouseError(f"giving up on {url}: {last_error}")

    # -- endpoints --------------------------------------------------------

    def search_companies(self, query: str, items_per_page: int = 20) -> list[dict]:
        resp = self._request(
            "GET",
            f"{REST_BASE}/search/companies",
            params={"q": query, "items_per_page": items_per_page},
        )
        if resp.status_code != 200:
            raise CompaniesHouseError(f"search failed ({resp.status_code}) for {query!r}")
        return resp.json().get("items", [])

    def company_profile(self, company_number: str) -> dict:
        resp = self._request("GET", f"{REST_BASE}/company/{company_number}")
        if resp.status_code != 200:
            raise CompaniesHouseError(
                f"profile failed ({resp.status_code}) for {company_number}"
            )
        return resp.json()

    def filing_history(
        self, company_number: str, category: str = "accounts", items_per_page: int = 100
    ) -> list[dict]:
        """All filings of a category, paging through the full history."""
        items: list[dict] = []
        start_index = 0
        while True:
            params = {"items_per_page": items_per_page, "start_index": start_index}
            if category:
                params["category"] = category
            resp = self._request(
                "GET",
                f"{REST_BASE}/company/{company_number}/filing-history",
                params=params,
            )
            if resp.status_code == 404:
                return items
            if resp.status_code != 200:
                raise CompaniesHouseError(
                    f"filing history failed ({resp.status_code}) for {company_number}"
                )
            payload = resp.json()
            page = payload.get("items", [])
            items.extend(page)
            start_index += len(page)
            if not page or start_index >= payload.get("total_count", 0):
                break
        return items

    def download_document(self, document_id: str) -> tuple[bytes, str]:
        """Fetch a filing document. Returns (content, content_type)."""
        resp = self._request(
            "GET",
            f"{DOC_BASE}/document/{document_id}/content",
            headers={"Accept": "application/pdf"},
        )
        if resp.status_code != 200:
            raise CompaniesHouseError(
                f"document download failed ({resp.status_code}) for {document_id}"
            )
        return resp.content, resp.headers.get("Content-Type", "")


def _backoff(attempt: int) -> float:
    """Exponential backoff with jitter. Deterministic seeding is irrelevant here —
    this only affects wall-clock timing, never pipeline output."""
    return min(2.0**attempt, 30.0) + random.uniform(0, 0.5)


def document_id_from_filing(filing: dict) -> str | None:
    """Filing history entries carry the document id inside a metadata URL."""
    link = (filing.get("links") or {}).get("document_metadata")
    if not link:
        return None
    return link.rstrip("/").rsplit("/", 1)[-1]
