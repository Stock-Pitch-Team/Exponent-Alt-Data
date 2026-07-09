"""CPSC recall acquisition via saferproducts.gov REST API (no key needed)."""
import json
import logging

from config.categories import CATEGORY_KEYWORDS, SEVERITY_WEIGHTS
from src.common import http

log = logging.getLogger(__name__)

BASE = "https://www.saferproducts.gov/RestWebServices/Recall"


def fetch_recalls(start_year: int, end_year: int, use_cache=True) -> list[dict]:
    """Fetch all CPSC recalls, year by year (keeps individual responses small)."""
    out = []
    for year in range(start_year, end_year + 1):
        params = {
            "RecallDateStart": f"{year}-01-01",
            "RecallDateEnd": f"{year}-12-31",
            "format": "json",
        }
        raw = http.cached_get(BASE, params=params, use_cache=use_cache)
        rows = json.loads(raw)
        out.extend(rows)
        log.info("CPSC %d: %d recalls", year, len(rows))
    return out


def _record_text(rec: dict) -> str:
    parts = [rec.get("Title") or "", rec.get("Description") or ""]
    for p in rec.get("Products") or []:
        parts.append(p.get("Name") or "")
        parts.append(p.get("Description") or "")
    for h in rec.get("Hazards") or []:
        parts.append(h.get("Name") or "")
    return " ".join(parts).lower()


def _has_injury(rec: dict) -> bool:
    for inj in rec.get("Injuries") or []:
        text = (inj.get("Name") or "").lower()
        if any(w in text for w in ("injur", "death", "died", "burn", "hospital",
                                   "lacerat", "fracture", "fatal")):
            # "no injuries reported" must not count
            if "no injuries" in text or "no incidents" in text:
                continue
            return True
    return False


def classify(recalls: list[dict]) -> list[dict]:
    """Tag each recall with categories, severity weight and quarter."""
    out = []
    for rec in recalls:
        date = (rec.get("RecallDate") or "")[:10]
        if not date:
            continue
        text = _record_text(rec)
        cats = [cat for cat, kws in CATEGORY_KEYWORDS.items()
                if any(kw in text for kw in kws)]
        if not cats:
            continue  # not Exponent-relevant
        injury = _has_injury(rec)
        weight = SEVERITY_WEIGHTS["cpsc_recall_injury" if injury else "cpsc_recall"]
        out.append({"date": date, "categories": cats, "weight": weight,
                    "source": "cpsc_recall", "injury": injury})
    return out
