"""Live consultant roster via the site's own public Meilisearch search backend.

The find-people page ships a public (read-only, search-scoped) Meilisearch
API key to every visitor; we page through the same index the site's JS
queries. Connection details are re-extracted from the page on each run so
key rotation doesn't break the pipeline.
"""
import json
import logging
import re

from bs4 import BeautifulSoup

from src.common import http

log = logging.getLogger(__name__)

FIND_PEOPLE_URL = "https://www.exponent.com/find-people"
_CLIENT_RE = re.compile(
    r'"search":\{"client":\{"apiUrl":"(?P<url>[^"]+)","apiKey":"(?P<key>[^"]+)"')

# Job-title bands, best-effort from bio text (coverage % is reported honestly)
_TITLE_RE = re.compile(
    r"\b(Group Vice President|Vice President|Principal Scientist|Principal Engineer|"
    r"Principal|Managing Scientist|Managing Engineer|Senior Managing Scientist|"
    r"Senior Managing Engineer|Senior Scientist|Senior Engineer|Senior Associate|"
    r"Senior Manager|Manager|Associate|Director)\b")

_BAND_ORDER = ["Vice President", "Principal", "Senior Managing", "Managing",
               "Senior", "Manager/Director", "Associate", "unknown"]


def _discover_client(use_cache=True):
    page = http.cached_get(FIND_PEOPLE_URL, use_cache=use_cache).decode("utf-8", "replace")
    m = _CLIENT_RE.search(page.replace("\\/", "/"))
    if not m:
        raise http.SourceUnavailable(FIND_PEOPLE_URL, "meilisearch client config not found in page")
    return m.group("url"), m.group("key")


def _band(title: str | None) -> str:
    if not title:
        return "unknown"
    if "Vice President" in title:
        return "Vice President"
    if "Principal" in title:
        return "Principal"
    if "Senior Managing" in title:
        return "Senior Managing"
    if "Managing" in title:
        return "Managing"
    if title.startswith("Senior"):
        return "Senior"
    if title in ("Manager", "Director"):
        return "Manager/Director"
    if "Associate" in title:
        return "Associate"
    return "unknown"


def fetch_roster(use_cache=True) -> dict:
    api_url, api_key = _discover_client(use_cache=use_cache)
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json"}
    search_url = f"{api_url.rstrip('/')}/indexes/production/search"
    people, page, total_hits = [], 1, None
    while True:
        body = {"q": "", "hitsPerPage": 100, "page": page,
                "filter": "subtype = Professional"}
        raw = http.cached_post_json(search_url, body, headers=headers,
                                    ttl_days=7, use_cache=use_cache)
        doc = json.loads(raw)
        total_hits = doc.get("totalHits")
        hits = doc.get("hits", [])
        for h in hits:
            people.append(_parse_person(h))
        if page >= doc.get("totalPages", 1):
            break
        page += 1
    log.info("live roster: %d people (index reports %s)", len(people), total_hits)
    return {"people": people, "total_hits": total_hits,
            "source_url": FIND_PEOPLE_URL, "search_backend": search_url}


def _parse_person(hit: dict) -> dict:
    teaser = BeautifulSoup(hit.get("teaser") or "", "html.parser")
    practice = None
    meta = teaser.select_one(".teaser-meta-person a[href^='/expertise/']")
    if meta:
        practice = meta.get_text(strip=True)
    summary = hit.get("summary") or ""
    m = _TITLE_RE.search(summary)
    title = m.group(0) if m else None
    return {
        "name": hit.get("title"),
        "slug": (hit.get("url") or "").rsplit("/", 1)[-1],
        "url": f"https://www.exponent.com{hit.get('url')}" if hit.get("url") else None,
        "practice": practice,
        "title_guess": title,
        "band": _band(title),
        "is_doctor": summary.startswith("Dr.") or " Ph.D" in summary[:200],
    }
