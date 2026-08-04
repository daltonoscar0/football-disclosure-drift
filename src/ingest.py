"""Stage 1: resolve club entities and download their three most recent full accounts.

Two phases, both idempotent:

  resolve   search Companies House for each club, pull the accounts filing history
            of plausible candidates, and rank them by whether they file *group*
            (consolidated) accounts. Writes data/entities.json.
  download  fetch the three most recent full-accounts PDFs per chosen entity into
            data/raw/<club>/<year>.pdf, plus data/raw/manifest.json.

Nothing is re-downloaded if it is already cached.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .ch_client import CompaniesHouseClient, MissingAPIKey, document_id_from_filing
from .util import ROOT, jdump

RAW = ROOT / "data" / "raw"
ENTITIES_PATH = ROOT / "data" / "entities.json"
MANIFEST_PATH = RAW / "manifest.json"

# Accounts filing types, best first. "group" means consolidated accounts, which is
# what we want: for Chelsea in particular the intra-group disposal profits only
# appear in the consolidated P&L of the holding company.
ACCOUNTS_RANK = {
    "accounts-with-accounts-type-group": 0,
    "accounts-with-accounts-type-full": 1,
    "accounts-with-accounts-type-medium": 2,
    "accounts-with-accounts-type-small": 3,
    "accounts-with-accounts-type-total-exemption-full": 4,
    "accounts-with-accounts-type-micro-entity": 5,
    "accounts-with-accounts-type-dormant": 6,
}
USABLE_TYPES = {
    "accounts-with-accounts-type-group",
    "accounts-with-accounts-type-full",
    "accounts-with-accounts-type-medium",
}

# Search terms per club. Deliberately broad: the point is to surface the holding
# companies alongside the operating companies so the ranker can compare them.
CLUBS: list[dict] = [
    {
        "slug": "chelsea",
        "name": "Chelsea",
        "queries": ["Chelsea FC", "Chelsea Football Club", "BlueCo 22", "Fordstam"],
    },
    {
        "slug": "arsenal",
        "name": "Arsenal",
        "queries": ["Arsenal Holdings", "Arsenal Football Club", "Arsenal FC"],
    },
    {
        "slug": "tottenham",
        "name": "Tottenham Hotspur",
        "queries": ["Tottenham Hotspur", "THFC Holdings", "ENIC Sports"],
    },
    {
        "slug": "west-ham",
        "name": "West Ham United",
        "queries": ["West Ham United", "WH Holding", "West Ham Football Club"],
    },
    {
        "slug": "everton",
        "name": "Everton",
        "queries": ["Everton Football Club", "Blue Heaven Holdings", "Everton FC"],
    },
]

# Candidates whose names match these are almost never the filing entity we want.
NAME_NOISE = (
    "supporters",
    "fan club",
    "ladies",
    "travel club",
    "foundation",
    "charitable",
    "community sports",
)


def _plausible(item: dict, club: dict) -> bool:
    """Cheap name/status filter, applied before any filing history is fetched.

    Substring matching is far too loose here: "wh" hits BESTWAY WHOLESALE, "blueco"
    hits THE BLUECOAT, and "chelsea" hits AGE UK KENSINGTON AND CHELSEA. A candidate
    must either *begin* with a query's leading word (ignoring a leading "The") or
    contain a full query phrase.
    """
    title = (item.get("title") or "").lower()
    if any(noise in title for noise in NAME_NOISE):
        return False
    if item.get("company_status") == "dissolved":
        return False

    stripped = re.sub(r"^the\s+", "", title)
    first_word = re.split(r"[\s,.]+", stripped, maxsplit=1)[0]
    for query in club["queries"]:
        q = query.lower()
        if first_word == q.split()[0]:
            return True
        if q in title:
            return True
    return False


def _accounts_summary(filings: list[dict]) -> dict:
    """Reduce a filing history to the signals we rank on."""
    usable = [
        f
        for f in filings
        if f.get("type") == "AA" and f.get("description") in ACCOUNTS_RANK
    ]
    usable.sort(key=lambda f: f.get("date", ""), reverse=True)
    recent = usable[:6]
    best_rank = min(
        (ACCOUNTS_RANK[f["description"]] for f in recent), default=len(ACCOUNTS_RANK)
    )
    return {
        "accounts_filings": len(usable),
        "recent_descriptions": [f.get("description") for f in recent],
        "best_rank": best_rank,
        "n_usable_recent": sum(
            1 for f in recent if f.get("description") in USABLE_TYPES
        ),
        "latest_date": recent[0].get("date") if recent else None,
    }


def resolve(client: CompaniesHouseClient) -> dict:
    """Search, inspect filing histories, and rank candidates for every club."""
    out: dict = {"clubs": {}}
    for club in CLUBS:
        seen: dict[str, dict] = {}
        for query in club["queries"]:
            for item in client.search_companies(query):
                number = item.get("company_number")
                if not number or number in seen:
                    continue
                if not _plausible(item, club):
                    continue
                seen[number] = item

        candidates = []
        for number in sorted(seen):
            item = seen[number]
            filings = client.filing_history(number)
            summary = _accounts_summary(filings)
            candidates.append(
                {
                    "company_number": number,
                    "title": item.get("title"),
                    "company_status": item.get("company_status"),
                    "date_of_creation": item.get("date_of_creation"),
                    **summary,
                }
            )

        # Rank: consolidated accounts first, then most usable recent filings, then
        # most recent. Company number breaks ties so the result is deterministic.
        candidates.sort(
            key=lambda c: (
                c["best_rank"],
                -c["n_usable_recent"],
                -_date_key(c["latest_date"]),
                c["company_number"],
            )
        )
        out["clubs"][club["slug"]] = {
            "name": club["name"],
            "candidates": candidates,
            "chosen": candidates[0]["company_number"] if candidates else None,
        }
        print(
            f"{club['slug']:<10} {len(candidates)} candidates, "
            f"chosen {out['clubs'][club['slug']]['chosen']}"
        )
    return out


def _date_key(date_str: str | None) -> int:
    if not date_str:
        return 0
    return int(date_str.replace("-", ""))


def _pick_filings(client: CompaniesHouseClient, company_number: str, n: int = 3) -> list[dict]:
    """The n most recent full/group accounts filings, newest first."""
    filings = [
        f
        for f in client.filing_history(company_number)
        if f.get("type") == "AA" and f.get("description") in USABLE_TYPES
    ]
    filings.sort(key=lambda f: (f.get("date", ""), f.get("transaction_id", "")), reverse=True)
    # One filing per made-up date: amended accounts for the same period would
    # otherwise crowd out an earlier year.
    picked: list[dict] = []
    seen_periods: set[str] = set()
    for f in filings:
        period = (f.get("description_values") or {}).get("made_up_date") or f.get("date", "")
        if period in seen_periods:
            continue
        seen_periods.add(period)
        picked.append(f)
        if len(picked) == n:
            break
    return picked


def _year_of(filing: dict) -> str:
    made_up = (filing.get("description_values") or {}).get("made_up_date")
    return (made_up or filing.get("date", ""))[:4]


def download(client: CompaniesHouseClient, entities: dict) -> dict:
    manifest: dict = {"filings": []}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    by_key = {(f["club"], f["year"]): f for f in manifest["filings"]}

    for slug in sorted(entities["clubs"]):
        entry = entities["clubs"][slug]
        number = entry.get("chosen")
        if not number:
            print(f"{slug}: no entity resolved, skipping", file=sys.stderr)
            continue
        club_dir = RAW / slug
        club_dir.mkdir(parents=True, exist_ok=True)

        for filing in _pick_filings(client, number):
            year = _year_of(filing)
            pdf_path = club_dir / f"{year}.pdf"
            record = {
                "club": slug,
                "year": year,
                "company_number": number,
                "company_name": entry.get("name"),
                "filing_date": filing.get("date"),
                "made_up_date": (filing.get("description_values") or {}).get("made_up_date"),
                "transaction_id": filing.get("transaction_id"),
                "accounts_type": filing.get("description"),
                "path": str(pdf_path.relative_to(ROOT)),
            }

            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                print(f"{slug} {year}: cached")
            else:
                doc_id = document_id_from_filing(filing)
                if not doc_id:
                    record["error"] = "no document_metadata link on filing"
                    print(f"{slug} {year}: no document link", file=sys.stderr)
                    by_key[(slug, year)] = record
                    continue
                content, content_type = client.download_document(doc_id)
                pdf_path.write_bytes(content)
                record["content_type"] = content_type
                print(f"{slug} {year}: downloaded {len(content):,} bytes")

            record["bytes"] = pdf_path.stat().st_size if pdf_path.exists() else 0
            by_key[(slug, year)] = record

    manifest["filings"] = [by_key[k] for k in sorted(by_key)]
    jdump(manifest, MANIFEST_PATH)
    return manifest


FILINGS_PER_CLUB = 3


def fully_cached() -> bool:
    """True when every expected filing is already on disk.

    Requires a resolved entity for each club and FILINGS_PER_CLUB downloaded files
    per club, so a partial cache still triggers a fetch rather than quietly
    proceeding with a short dataset.
    """
    if not ENTITIES_PATH.exists() or not MANIFEST_PATH.exists():
        return False
    entities = json.loads(ENTITIES_PATH.read_text())
    clubs = entities.get("clubs", {})
    if sorted(clubs) != sorted(c["slug"] for c in CLUBS):
        return False
    if any(not entry.get("chosen") for entry in clubs.values()):
        return False

    manifest = json.loads(MANIFEST_PATH.read_text())
    present: dict[str, int] = {}
    for record in manifest.get("filings", []):
        path = ROOT / record["path"]
        if path.exists() and path.stat().st_size > 0:
            present[record["club"]] = present.get(record["club"], 0) + 1
    return all(present.get(slug, 0) >= FILINGS_PER_CLUB for slug in clubs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resolve-only", action="store_true")
    ap.add_argument(
        "--reresolve",
        action="store_true",
        help="re-run entity resolution even if data/entities.json exists",
    )
    args = ap.parse_args(argv)

    # An API key is only needed to fetch something we do not already have. Requiring
    # it unconditionally would make `make pipeline` fail offline on a fully cached
    # checkout, which is exactly the case the cache exists to support.
    if not args.reresolve and fully_cached():
        print(f"all filings already cached in {RAW.relative_to(ROOT)} — nothing to fetch")
        return 0

    try:
        client = CompaniesHouseClient()
    except MissingAPIKey as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if ENTITIES_PATH.exists() and not args.reresolve:
        entities = json.loads(ENTITIES_PATH.read_text())
        print(f"using cached entity resolution ({ENTITIES_PATH})")
    else:
        entities = resolve(client)
        jdump(entities, ENTITIES_PATH)

    if args.resolve_only:
        return 0

    manifest = download(client, entities)
    ok = sum(1 for f in manifest["filings"] if f.get("bytes"))
    print(f"\n{ok}/{len(manifest['filings'])} filings present in data/raw/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
