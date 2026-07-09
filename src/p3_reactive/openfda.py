"""openFDA acquisition: device recalls (enforcement) + MAUDE adverse events.

Uses count aggregations only — never pages through millions of raw events.
All FDA device data maps to the 'medical_device' category by definition.
"""
import json
import logging

from config import settings
from config.categories import SEVERITY_WEIGHTS
from src.common import http

log = logging.getLogger(__name__)

ENFORCEMENT = "https://api.fda.gov/device/enforcement.json"
MAUDE = "https://api.fda.gov/device/event.json"

CLASS_WEIGHTS = {
    "Class I": SEVERITY_WEIGHTS["fda_recall_class_1"],
    "Class II": SEVERITY_WEIGHTS["fda_recall_class_2"],
    "Class III": SEVERITY_WEIGHTS["fda_recall_class_3"],
}
EVENT_WEIGHTS = {
    "Death": SEVERITY_WEIGHTS["maude_death"],
    "Injury": SEVERITY_WEIGHTS["maude_injury"],
    "Malfunction": SEVERITY_WEIGHTS["maude_malfunction"],
}


def _params(extra: dict) -> dict:
    p = dict(extra)
    if settings.OPENFDA_API_KEY:
        p["api_key"] = settings.OPENFDA_API_KEY
    return p


def _count(url: str, search: str, count_field: str, use_cache=True) -> list[dict]:
    try:
        raw = http.cached_get(url, params=_params({"search": search, "count": count_field}),
                              use_cache=use_cache)
    except http.SourceUnavailable as exc:
        if "404" in exc.reason:  # openFDA returns 404 for zero-result windows
            return []
        raise
    return json.loads(raw).get("results", [])


def recalls_by_quarter(quarters, use_cache=True) -> list[dict]:
    """[(label, start_iso, end_iso)] -> weighted Class I/II/III counts per quarter."""
    out = []
    for label, start, end in quarters:
        search = f"recall_initiation_date:[{start.replace('-', '')} TO {end.replace('-', '')}]"
        try:
            buckets = _count(ENFORCEMENT, search, "classification.exact", use_cache)
        except http.SourceUnavailable as exc:
            log.warning("openFDA enforcement %s failed: %s", label, exc)
            out.append({"quarter": label, "status": "missing"})
            continue
        counts = {b["term"]: b["count"] for b in buckets}
        weighted = sum(CLASS_WEIGHTS.get(cls, 1.0) * n for cls, n in counts.items())
        out.append({"quarter": label, "counts": counts, "weighted": weighted,
                    "total": sum(counts.values())})
    return out


def maude_by_quarter(quarters, use_cache=True) -> list[dict]:
    out = []
    for label, start, end in quarters:
        search = f"date_received:[{start.replace('-', '')} TO {end.replace('-', '')}]"
        try:
            buckets = _count(MAUDE, search, "event_type.exact", use_cache)
        except http.SourceUnavailable as exc:
            log.warning("openFDA MAUDE %s failed: %s", label, exc)
            out.append({"quarter": label, "status": "missing"})
            continue
        counts = {b["term"]: b["count"] for b in buckets}
        weighted = sum(EVENT_WEIGHTS.get(t, 0.25) * n for t, n in counts.items())
        out.append({"quarter": label, "counts": counts, "weighted": weighted,
                    "total": sum(counts.values())})
    return out
