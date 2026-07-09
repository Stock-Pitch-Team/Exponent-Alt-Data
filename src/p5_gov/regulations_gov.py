"""Regulations.gov v4 acquisition: rulemaking documents/comments mentioning Exponent.

Counting strategy (keeps requests small and avoids the 5,000-result window):
- 'strict' series: quoted phrase searches that can only mean the firm
  ("Exponent, Inc" / "prepared by Exponent"), one count request per year.
- 'raw' series: bare word "Exponent" (includes math false positives), for
  transparency about how much the strict filter removes.
Counts come from meta.totalElements; a capped number of evidence pages is
fetched for the on-site table.
"""
import json
import logging

from config import settings
from src.common import http

log = logging.getLogger(__name__)

BASE = "https://api.regulations.gov/v4"
STRICT_PHRASES = ['"Exponent, Inc"', '"prepared by Exponent"']
RAW_TERM = "Exponent"


def _get(endpoint: str, params: dict, use_cache=True) -> dict:
    params = dict(params)
    params["api_key"] = settings.REGULATIONS_GOV_API_KEY
    raw = http.cached_get(f"{BASE}/{endpoint}", params=params, use_cache=use_cache)
    return json.loads(raw)


def _count(endpoint: str, term: str, year: int, use_cache=True) -> int:
    doc = _get(endpoint, {
        "filter[searchTerm]": term,
        "filter[postedDate][ge]": f"{year}-01-01",
        "filter[postedDate][le]": f"{year}-12-31",
        "page[size]": 5,
    }, use_cache=use_cache)
    return int(doc.get("meta", {}).get("totalElements", 0))


def _total(endpoint: str, year: int, use_cache=True) -> int:
    """All items posted in a year (no search term) — the normalization denominator."""
    doc = _get(endpoint, {
        "filter[postedDate][ge]": f"{year}-01-01",
        "filter[postedDate][le]": f"{year}-12-31",
        "page[size]": 5,
    }, use_cache=use_cache)
    return int(doc.get("meta", {}).get("totalElements", 0))


def yearly_counts(start_year: int, end_year: int, use_cache=True) -> list[dict]:
    out = []
    for year in range(start_year, end_year + 1):
        row = {"year": year}
        for endpoint in ("documents", "comments"):
            try:
                strict = sum(_count(endpoint, p, year, use_cache) for p in STRICT_PHRASES)
                raw = _count(endpoint, RAW_TERM, year, use_cache)
                total = _total(endpoint, year, use_cache)
            except http.SourceUnavailable as exc:
                log.warning("regulations.gov %s %d failed: %s", endpoint, year, exc)
                row[endpoint] = None
                continue
            row[endpoint] = {"strict": strict, "raw": raw, "total_posted": total,
                             "strict_per_10k": round(strict / total * 10000, 2) if total else None}
        out.append(row)
        log.info("regulations.gov %d: %s", year, {k: v for k, v in row.items() if k != 'year'})
    return out


def evidence_sample(max_pages: int = 6, use_cache=True) -> list[dict]:
    """Most recent strictly-matching documents for the on-site evidence table."""
    rows = []
    for phrase in STRICT_PHRASES:
        for page in range(1, max_pages // len(STRICT_PHRASES) + 1):
            try:
                doc = _get("documents", {
                    "filter[searchTerm]": phrase,
                    "page[size]": 100,
                    "page[number]": page,
                    "sort": "-postedDate",
                }, use_cache=use_cache)
            except http.SourceUnavailable as exc:
                log.warning("evidence page failed: %s", exc)
                break
            batch = doc.get("data", [])
            for d in batch:
                a = d.get("attributes", {})
                rows.append({
                    "id": d.get("id"),
                    "title": (a.get("title") or "")[:300],
                    "agency": a.get("agencyId"),
                    "docket": a.get("docketId"),
                    "type": a.get("documentType"),
                    "posted": (a.get("postedDate") or "")[:10],
                    "matched_phrase": phrase,
                    "url": f"https://www.regulations.gov/document/{d.get('id')}",
                })
            if len(batch) < 100:
                break
    seen, unique = set(), []
    for r in sorted(rows, key=lambda r: r["posted"], reverse=True):
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        unique.append(r)
    return unique
