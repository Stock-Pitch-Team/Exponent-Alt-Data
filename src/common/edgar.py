"""Shared SEC EDGAR client: company tickers, XBRL companyfacts, XBRL frames.

SEC requires a User-Agent identifying the requester (set in http.py) and
asks for <=10 requests/second (throttled in settings.RATE_LIMITS).
"""
import json
import re

from src.common import http

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json"
FRAMES_URL = "https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{frame}.json"

_FRAME_QUARTER = re.compile(r"^CY(\d{4})Q([1-4])$")
_FRAME_ANNUAL = re.compile(r"^CY(\d{4})$")


def all_tickers() -> dict:
    """Return {ticker: {cik_str, ticker, title}} from SEC's official mapping."""
    raw = http.cached_get(TICKERS_URL)
    entries = json.loads(raw)
    return {v["ticker"].upper(): v for v in entries.values()}


def cik_for_ticker(ticker: str) -> int:
    entry = all_tickers().get(ticker.upper())
    if entry is None:
        raise KeyError(f"ticker {ticker} not found in SEC mapping")
    return int(entry["cik_str"])


def companyfacts(cik: int) -> dict:
    raw = http.cached_get(COMPANYFACTS_URL.format(cik=cik))
    return json.loads(raw)


def frames(tag: str, frame: str) -> dict:
    """XBRL frame: every filer's value for one tag in one period, e.g. CY2024."""
    raw = http.cached_get(FRAMES_URL.format(tag=tag, frame=frame))
    return json.loads(raw)


def quarterly_series(facts: dict, tag: str, unit: str = "USD",
                     namespace: str = "us-gaap") -> list[dict]:
    """Extract deduplicated quarterly values for a tag from companyfacts.

    Uses SEC's own 'frame' annotations (CYyyyyQq) which mark the canonical,
    deduplicated value for each calendar quarter.
    """
    try:
        entries = facts["facts"][namespace][tag]["units"][unit]
    except KeyError:
        return []
    out = {}
    for e in entries:
        frame = e.get("frame") or ""
        m = _FRAME_QUARTER.match(frame)
        if not m:
            continue
        label = f"{m.group(1)}-Q{m.group(2)}"
        out[label] = {"period": label, "value": e["val"], "end": e.get("end"),
                      "filed": e.get("filed"), "form": e.get("form")}
    return [out[k] for k in sorted(out)]


def annual_series(facts: dict, tag: str, unit: str = "USD",
                  namespace: str = "us-gaap") -> list[dict]:
    try:
        entries = facts["facts"][namespace][tag]["units"][unit]
    except KeyError:
        return []
    out = {}
    for e in entries:
        frame = e.get("frame") or ""
        m = _FRAME_ANNUAL.match(frame)
        if not m:
            continue
        label = m.group(1)
        out[label] = {"period": label, "value": e["val"], "end": e.get("end"),
                      "filed": e.get("filed"), "form": e.get("form")}
    return [out[k] for k in sorted(out)]


def first_available_series(facts: dict, tags: list[str], kind: str = "quarterly"):
    """Try tags in order; return (tag_used, series) for the first with data."""
    fn = quarterly_series if kind == "quarterly" else annual_series
    for tag in tags:
        series = fn(facts, tag)
        if series:
            return tag, series
    return None, []
