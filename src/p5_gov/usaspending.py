"""USAspending.gov acquisition: federal awards to Exponent, Inc (no key needed)."""
import json
import logging

from config import entities
from src.common import http, names

log = logging.getLogger(__name__)

BASE = "https://api.usaspending.gov/api/v2"
AWARD_TYPE_CODES = ["A", "B", "C", "D"]  # contracts + IDVs orders
FIELDS = ["Award ID", "Recipient Name", "Start Date", "End Date", "Award Amount",
          "Awarding Agency", "Awarding Sub Agency", "Description",
          "recipient_id", "generated_internal_id"]


def resolve_recipients(use_cache=True) -> list[dict]:
    """Find candidate recipient records for Exponent (and legacy name)."""
    found = []
    for text in ("EXPONENT", "FAILURE ANALYSIS ASSOCIATES"):
        raw = http.cached_post_json(f"{BASE}/autocomplete/recipient/",
                                    {"search_text": text, "limit": 20},
                                    use_cache=use_cache)
        doc = json.loads(raw)
        for r in doc.get("results", []):
            found.append(r)
    return found


def _is_exponent(recipient_name: str) -> bool:
    norm = names.normalize_company(recipient_name or "")
    return norm in ("exponent", "failure analysis associates",
                    "exponent failure analysis associates")


def fetch_awards(start_fy: int, end_fy: int, use_cache=True) -> list[dict]:
    """Award-level rows where the recipient name matches Exponent exactly."""
    awards = []
    for fy in range(start_fy, end_fy + 1):
        page = 1
        while True:
            body = {
                "filters": {
                    "recipient_search_text": ["Exponent"],
                    "time_period": [{"start_date": f"{fy-1}-10-01",
                                     "end_date": f"{fy}-09-30"}],
                    "award_type_codes": AWARD_TYPE_CODES,
                },
                "fields": FIELDS,
                "limit": 100,
                "page": page,
                "order": "desc",
                "sort": "Award Amount",
            }
            raw = http.cached_post_json(f"{BASE}/search/spending_by_award/", body,
                                        use_cache=use_cache)
            doc = json.loads(raw)
            results = doc.get("results", [])
            for r in results:
                if _is_exponent(r.get("Recipient Name")):
                    r["fiscal_year"] = fy
                    awards.append(r)
            if not doc.get("page_metadata", {}).get("hasNext") or page >= 10:
                break
            page += 1
        log.info("USAspending FY%d: %d Exponent awards so far", fy, len(awards))
    return awards
