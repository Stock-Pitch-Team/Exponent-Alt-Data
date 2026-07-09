"""Wayback CDX census of Exponent staff-profile URLs.

Headcount proxy: a profile URL's archive lifetime (first capture .. last
capture) approximates the consultant's tenure window on the site. The
per-year roster proxy counts URLs whose lifetime covers that year.
Two URL eras are covered (site redesigns):
  /professionals/{a-z}/{last-first}   (~2005-2022)
  /people/{first-last}                (2023-now)
"""
import logging
import re
from collections import defaultdict

from src.common import http

log = logging.getLogger(__name__)

CDX_URL = "http://web.archive.org/cdx/search/cdx"

ERAS = {
    # urlkeys are SURT format: "com,exponent)/people/rob-sunley"
    "professionals": {
        "pattern": "exponent.com/professionals/*",
        "slug_re": re.compile(r"^com,exponent\)/professionals/[a-z]/([a-z0-9-]+)$"),
    },
    "people": {
        "pattern": "exponent.com/people/*",
        "slug_re": re.compile(r"^com,exponent\)/people/([a-z0-9-]+)$"),
    },
}


def _cdx_rows(pattern: str, use_cache=True):
    """Yield (urlkey, timestamp) for all 200-status captures of a URL pattern."""
    resume_key = None
    page = 0
    while True:
        params = {
            "url": pattern,
            "fl": "urlkey,timestamp",
            "filter": "statuscode:200",
            "output": "text",
            "limit": 30000,
            "showResumeKey": "true",
        }
        if resume_key:
            params["resumeKey"] = resume_key
        raw = http.cached_get(CDX_URL, params=params, use_cache=use_cache)
        text = raw.decode("utf-8", "replace")
        lines = text.splitlines()
        resume_key = None
        blank_seen = False
        for line in lines:
            if not line.strip():
                blank_seen = True
                continue
            if blank_seen:
                resume_key = line.strip()
                break
            parts = line.split(" ")
            if len(parts) >= 2:
                yield parts[0], parts[1]
        page += 1
        log.info("CDX %s: page %d (%d lines)%s", pattern, page, len(lines),
                 " [more]" if resume_key else "")
        if not resume_key:
            return


def census(use_cache=True) -> dict:
    """Per-era, per-slug first/last capture timestamps."""
    eras = {}
    for era, cfg in ERAS.items():
        slugs: dict = {}
        rows = 0
        for urlkey, ts in _cdx_rows(cfg["pattern"], use_cache=use_cache):
            m = cfg["slug_re"].match(urlkey)
            if not m:
                continue
            slug = m.group(1)
            # filter junk: template artifacts, pagination, non-person paths
            if len(slug) < 4 or "-" not in slug or slug.startswith(("page-", "index")):
                continue
            year = int(ts[:4])
            rows += 1
            slot = slugs.setdefault(slug, {"first": year, "last": year, "captures": 0})
            slot["first"] = min(slot["first"], year)
            slot["last"] = max(slot["last"], year)
            slot["captures"] += 1
        eras[era] = slugs
        log.info("CDX era %s: %d profile slugs from %d captures", era, len(slugs), rows)
    return eras


def _token_key(slug: str) -> str:
    """Order-insensitive person key: legacy slugs are last-first, current are
    first-last, so sorting the name tokens makes the same person match across eras."""
    return ",".join(sorted(slug.split("-")))


def yearly_series(eras: dict, current_year: int) -> list[dict]:
    """Roster proxy per year: URLs whose capture lifetime covers the year.
    The combined line deduplicates the same person across URL eras."""
    out = []
    for year in range(2004, current_year + 1):
        row = {"year": year}
        combined: set = set()
        for era, slugs in eras.items():
            active = {slug for slug, s in slugs.items()
                      if s["first"] <= year <= s["last"]}
            row[f"{era}_active"] = len(active)
            combined.update(_token_key(slug) for slug in active)
        row["active_profiles"] = len(combined)
        out.append(row)
    return out


def joiners_leavers(eras: dict, current_year: int) -> list[dict]:
    """First-capture year ~ join proxy; last-capture year ~ leave proxy."""
    first_by_year = defaultdict(int)
    last_by_year = defaultdict(int)
    for era, slugs in eras.items():
        for s in slugs.values():
            first_by_year[s["first"]] += 1
            # last capture in the current era's final years just means 'still there'
            last_by_year[s["last"]] += 1
    out = []
    for year in range(2004, current_year + 1):
        out.append({"year": year, "new_profiles": first_by_year.get(year, 0),
                    "disappeared_profiles": last_by_year.get(year, 0)})
    return out
