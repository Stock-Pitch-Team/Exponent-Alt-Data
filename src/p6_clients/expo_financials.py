"""EXPO's own reported financials from SEC EDGAR XBRL (feeds P3 overlays, P6, exec summary)."""
import logging
from datetime import datetime, timezone

from config import entities
from src.common import edgar, http, jsonio, provenance

log = logging.getLogger(__name__)

def _fill_q4_from_annual(quarterly: list[dict], annual: list[dict]) -> list[dict]:
    """Fill missing Q4 points as annual minus Q1-Q3 (same filings, flagged derived)."""
    if not quarterly or not annual:
        return quarterly
    by_period = {p["period"]: p for p in quarterly}
    for a in annual:
        year = a["period"]
        q4 = f"{year}-Q4"
        if q4 in by_period:
            continue
        q123 = [by_period.get(f"{year}-Q{i}") for i in (1, 2, 3)]
        if any(p is None for p in q123):
            continue
        by_period[q4] = {"period": q4, "value": a["value"] - sum(p["value"] for p in q123),
                         "end": a.get("end"), "filed": a.get("filed"),
                         "form": a.get("form"), "derived": True}
    return [by_period[k] for k in sorted(by_period)]


REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
]
NET_INCOME_TAGS = ["NetIncomeLoss"]
EPS_TAGS = ["EarningsPerShareDiluted"]


def run(use_cache=True):
    try:
        cik = edgar.cik_for_ticker(entities.EXPO_TICKER)
        facts = edgar.companyfacts(cik)
    except (http.SourceUnavailable, KeyError) as exc:
        jsonio.write_site_json(
            "p6_expo_financials.json",
            provenance.envelope(
                pipeline="p6_clients", output="expo_financials", status="unavailable",
                status_reason=f"SEC EDGAR fetch failed: {exc}", sources=[], coverage=None,
                caveats=["No data fetched; nothing shown rather than fabricated data."],
                methodology_id="p6_expo_financials"),
            None)
        return None

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rev_tag, rev_q = edgar.first_available_series(facts, REVENUE_TAGS, "quarterly")
    _, rev_a = edgar.first_available_series(facts, REVENUE_TAGS, "annual")
    ni_tag, ni_q = edgar.first_available_series(facts, NET_INCOME_TAGS, "quarterly")
    # EPS lives under the USD/shares unit, not USD
    eps_q = edgar.quarterly_series(facts, "EarningsPerShareDiluted", unit="USD/shares")

    rev_q = _fill_q4_from_annual(rev_q, rev_a)
    ni_q = _fill_q4_from_annual(ni_q, edgar.annual_series(facts, ni_tag) if ni_tag else [])

    status = "ok" if rev_q else "partial"
    coverage = ({"start": rev_q[0]["period"], "end": rev_q[-1]["period"]}
                if rev_q else None)
    jsonio.write_site_json(
        "p6_expo_financials.json",
        provenance.envelope(
            pipeline="p6_clients", output="expo_financials", status=status,
            status_reason=None if rev_q else "no quarterly revenue frames found",
            sources=[provenance.source(
                f"SEC EDGAR XBRL companyfacts (CIK {cik}, {facts.get('entityName')})",
                edgar.COMPANYFACTS_URL.format(cik=cik), fetched_at=fetched_at,
                note=f"revenue tag: {rev_tag}; net income tag: {ni_tag}")],
            coverage=coverage,
            caveats=[
                "Values are exactly as Exponent reported them to the SEC in 10-Q/10-K filings (XBRL 'frame' values, deduplicated by the SEC).",
                "Quarterly history starts when XBRL tagging became mandatory (~2009-2011); older quarters are not available in this dataset.",
                "Segment-level revenue is not exposed in the XBRL companyfacts API, so only company totals are shown.",
                "Where the SEC data lacks a Q4 value (the annual report carries the full-year figure instead), Q4 is computed as full-year minus Q1+Q2+Q3 from the same filings; these points are flagged 'derived': true.",
            ],
            methodology_id="p6_expo_financials"),
        {"revenue_quarterly": rev_q, "revenue_annual": rev_a,
         "net_income_quarterly": ni_q, "eps_diluted_quarterly": eps_q,
         "cik": cik, "entity_name": facts.get("entityName")},
    )
    log.info("EXPO financials: %d quarterly revenue points (%s..%s)",
             len(rev_q), rev_q[0]["period"] if rev_q else "-",
             rev_q[-1]["period"] if rev_q else "-")
    return {"revenue_quarterly": rev_q, "cik": cik}
