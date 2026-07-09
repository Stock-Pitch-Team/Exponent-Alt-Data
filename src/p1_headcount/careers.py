"""Open job postings snapshot from Exponent's careers search (same Meilisearch backend
if indexed) or the careers page. Hiring-intent signal; history accumulates going forward."""
import json
import logging

from src.common import http
from src.p1_headcount.live_roster import _discover_client

log = logging.getLogger(__name__)


def fetch_postings(use_cache=True) -> dict:
    """Try the site search index for job postings; fall back to careers page scan."""
    api_url, api_key = _discover_client(use_cache=use_cache)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    search_url = f"{api_url.rstrip('/')}/indexes/production/search"

    # discover available subtypes to find a job/career content type
    raw = http.cached_post_json(search_url, {"q": "", "hitsPerPage": 1, "page": 1,
                                             "facets": ["subtype"]},
                                headers=headers, ttl_days=7, use_cache=use_cache)
    doc = json.loads(raw)
    facets = (doc.get("facetDistribution") or {}).get("subtype") or {}
    log.info("search index subtypes: %s", facets)
    job_subtype = next((s for s in facets if "job" in s.lower()
                        or "career" in s.lower() or "opening" in s.lower()), None)
    if not job_subtype:
        return {"postings": [], "subtypes_seen": facets,
                "note": "no job content type in site search index"}

    postings, page = [], 1
    while True:
        raw = http.cached_post_json(search_url, {
            "q": "", "hitsPerPage": 100, "page": page,
            "filter": f"subtype = {json.dumps(job_subtype)}"},
            headers=headers, ttl_days=7, use_cache=use_cache)
        doc = json.loads(raw)
        for h in doc.get("hits", []):
            postings.append({"title": h.get("title"), "url": h.get("url"),
                             "summary": (h.get("summary") or "")[:300]})
        if page >= doc.get("totalPages", 1):
            break
        page += 1
    return {"postings": postings, "subtypes_seen": facets, "job_subtype": job_subtype}
