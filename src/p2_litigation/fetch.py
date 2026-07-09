"""CourtListener v4 search acquisition with a daily request ledger.

Strategy: result volumes are small (~1.4k opinions, ~1.9k RECAP cases in
total), so we page through actual results year by year and keep case-level
metadata, rather than settling for bare counts. Every network request is
recorded in a daily ledger; when the free-tier budget is exhausted the run
stops cleanly and resumes from cache next time.
"""
import json
import logging
from datetime import date

from config import settings
from src.common import cache, http

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
OPINION_URL = "https://www.courtlistener.com/api/rest/v4/opinions/{id}/"
QUOTA_FILE = settings.INTERIM_DIR / "p2_quota.json"
DAILY_BUDGET = 4500  # generous; real cap enforced server-side via 429 + Retry-After

LOOSE_TERMS = ('expert OR witness OR testimony OR testified OR retained '
               'OR deposition OR "Rule 702" OR Daubert')
Q_LOOSE = f"Exponent AND ({LOOSE_TERMS})"
Q_STRICT = f'("Exponent, Inc." OR "Exponent Inc.") AND ({LOOSE_TERMS})'
Q_LEGACY = '"Failure Analysis Associates"'
Q_DAUBERT = 'Exponent AND (Daubert OR "Rule 702") AND (expert OR exclude OR admissib)'
Q_DAUBERT_BASELINE = '(Daubert OR "Rule 702") AND "motion to exclude" AND NOT Exponent'


class QuotaExhausted(Exception):
    pass


def _ledger() -> dict:
    if QUOTA_FILE.exists():
        return json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    return {}


def _record_request():
    led = _ledger()
    today = date.today().isoformat()
    led[today] = led.get(today, 0) + 1
    QUOTA_FILE.write_text(json.dumps(led, indent=0), encoding="utf-8")
    if led[today] > DAILY_BUDGET:
        raise QuotaExhausted(f"daily request budget {DAILY_BUDGET} reached")


def _headers():
    h = {}
    if settings.COURTLISTENER_API_TOKEN:
        h["Authorization"] = f"Token {settings.COURTLISTENER_API_TOKEN}"
    return h


def cl_get(url: str, params=None) -> dict:
    """Cached GET that only spends quota on cache misses."""
    key = cache.cache_key("GET", url, params)
    hit = cache.get(key)
    if hit is not None:
        return json.loads(hit[0])
    _record_request()
    raw = http.cached_get(url, params=params, headers=_headers(), ttl_days=90)
    return json.loads(raw)


def count(q: str | None, type_: str, year: int | None = None) -> int:
    params = {"type": type_, "count": "on"}
    if q:
        params["q"] = q
    if year:
        params["filed_after"] = f"{year}-01-01"
        params["filed_before"] = f"{year}-12-31"
    return int(cl_get(SEARCH_URL, params).get("count", 0))


def search_year(q: str, type_: str, year: int, max_pages: int = 30):
    """Yield slim result records for one query in one filed-year."""
    params = {"q": q, "type": type_,
              "filed_after": f"{year}-01-01", "filed_before": f"{year}-12-31"}
    doc = cl_get(SEARCH_URL, params)
    pages = 1
    while True:
        for r in doc.get("results", []):
            yield _slim(r, type_)
        nxt = doc.get("next")
        if not nxt or pages >= max_pages:
            if nxt:
                log.warning("truncated paging %s %s %d at %d pages", q[:30], type_, year, pages)
            return
        doc = cl_get(nxt)
        pages += 1


def _slim(r: dict, type_: str) -> dict:
    out = {
        "case_name": r.get("caseName"),
        "court": r.get("court"),
        "court_id": r.get("court_id"),
        "date_filed": r.get("dateFiled"),
        "docket_number": r.get("docketNumber"),
        "url": "https://www.courtlistener.com" + (r.get("absolute_url") or ""),
        "type": type_,
    }
    if type_ == "o":
        out["cluster_id"] = r.get("cluster_id")
        ops = r.get("opinions") or []
        out["opinion_ids"] = [o.get("id") for o in ops if o.get("id")]
        out["snippets"] = [(o.get("snippet") or "")[:600] for o in ops][:2]
    else:
        out["docket_id"] = r.get("docket_id")
        docs = r.get("recap_documents") or []
        out["snippets"] = [(d.get("snippet") or "")[:600] for d in docs][:2]
    return out


def opinion_text(opinion_id: int) -> str:
    doc = cl_get(OPINION_URL.format(id=opinion_id))
    return (doc.get("plain_text") or doc.get("html_with_citations")
            or doc.get("html") or "")
