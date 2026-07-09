"""OpenAlex acquisition: all works and authors affiliated with Exponent (I13383945)."""
import json
import logging

from config import entities, settings
from src.common import http

log = logging.getLogger(__name__)

BASE = "https://api.openalex.org"
WORKS_SELECT = ",".join([
    "id", "display_name", "publication_year", "publication_date",
    "cited_by_count", "authorships", "primary_topic", "type",
])


def _paginate(endpoint: str, filt: str, select: str | None = None, use_cache=True):
    cursor = "*"
    pages = 0
    while cursor:
        params = {
            "filter": filt,
            "per-page": 200,
            "cursor": cursor,
            "mailto": settings.CONTACT_EMAIL,
        }
        if select:
            params["select"] = select
        raw = http.cached_get(f"{BASE}/{endpoint}", params=params, use_cache=use_cache)
        doc = json.loads(raw)
        pages += 1
        for row in doc.get("results", []):
            yield row
        cursor = doc.get("meta", {}).get("next_cursor")
        if pages % 5 == 0:
            log.info("%s: fetched %d pages", endpoint, pages)


def fetch_works(use_cache=True) -> list[dict]:
    filt = f"authorships.institutions.id:{entities.OPENALEX_INSTITUTION_ID}"
    works = list(_paginate("works", filt, select=WORKS_SELECT, use_cache=use_cache))
    log.info("fetched %d works", len(works))
    return works


def fetch_authors(use_cache=True) -> list[dict]:
    filt = f"affiliations.institution.id:{entities.OPENALEX_INSTITUTION_ID}"
    authors = list(_paginate("authors", filt, use_cache=use_cache))
    log.info("fetched %d authors", len(authors))
    return authors
