"""Standard metadata envelope for every data/site output file.

The envelope is the enforcement mechanism for the no-fabrication rule:
every published number carries its source, fetch time, record counts and
an explicit ok/partial/unavailable status.
"""
from datetime import datetime, timezone

VALID_STATUSES = ("ok", "partial", "unavailable")


def source(name: str, url: str, *, fetched_at=None, records_scanned=None,
           records_matched=None, snapshot=None, note=None) -> dict:
    s = {"name": name, "url": url}
    if fetched_at:
        s["fetched_at"] = fetched_at
    if records_scanned is not None:
        s["records_scanned"] = records_scanned
    if records_matched is not None:
        s["records_matched"] = records_matched
    if snapshot:
        s["snapshot"] = snapshot
    if note:
        s["note"] = note
    return s


def envelope(*, pipeline: str, output: str, status: str, sources: list,
             coverage: dict | None, caveats: list, methodology_id: str,
             status_reason: str | None = None) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status {status!r}")
    if status != "ok" and not status_reason:
        raise ValueError("non-ok status requires status_reason")
    if not caveats:
        raise ValueError("caveats must be non-empty — every dataset has limitations")
    if status != "unavailable" and not sources:
        raise ValueError("sources must be non-empty for ok/partial outputs")
    return {
        "pipeline": pipeline,
        "output": output,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "status_reason": status_reason,
        "sources": sources,
        "coverage": coverage,
        "caveats": caveats,
        "methodology_id": methodology_id,
    }
