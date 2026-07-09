"""P5 build: federal awards + regulatory footprint site outputs."""
import logging
from collections import defaultdict
from datetime import date, datetime, timezone

from src.common import http, jsonio, provenance
from src.p5_gov import regulations_gov, usaspending

log = logging.getLogger(__name__)

START_FY = 2008
REGS_START_YEAR = 2005


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(step=None, use_cache=True):
    if step in (None, "awards"):
        _build_awards(use_cache)
    if step in (None, "regulations"):
        _build_regulations(use_cache)


def _build_awards(use_cache):
    end_fy = date.today().year + (1 if date.today().month >= 10 else 0)
    try:
        recipients = usaspending.resolve_recipients(use_cache=use_cache)
        awards = usaspending.fetch_awards(START_FY, end_fy, use_cache=use_cache)
    except http.SourceUnavailable as exc:
        jsonio.write_site_json(
            "p5_federal_awards.json",
            provenance.envelope(
                pipeline="p5_gov", output="federal_awards", status="unavailable",
                status_reason=f"USAspending fetch failed: {exc}", sources=[],
                coverage=None,
                caveats=["No data fetched; nothing shown rather than fabricated data."],
                methodology_id="p5_federal_awards"),
            None)
        return

    by_fy = defaultdict(lambda: {"obligations": 0.0, "awards": 0})
    by_agency = defaultdict(lambda: {"obligations": 0.0, "awards": 0})
    for a in awards:
        amt = float(a.get("Award Amount") or 0)
        fy = a["fiscal_year"]
        by_fy[fy]["obligations"] += amt
        by_fy[fy]["awards"] += 1
        agency = a.get("Awarding Agency") or "Unknown"
        by_agency[agency]["obligations"] += amt
        by_agency[agency]["awards"] += 1

    top_awards = sorted(awards, key=lambda a: -float(a.get("Award Amount") or 0))[:40]
    jsonio.write_site_json(
        "p5_federal_awards.json",
        provenance.envelope(
            pipeline="p5_gov", output="federal_awards",
            status="ok" if awards else "partial",
            status_reason=None if awards else "no awards matched the exact recipient name",
            sources=[provenance.source(
                "USAspending.gov award search (recipient name = Exponent, Inc)",
                "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                fetched_at=_now(), records_matched=len(awards),
                note=f"recipient candidates seen: {len(recipients)}")],
            coverage={"start": f"FY{START_FY}", "end": f"FY{end_fy}"},
            caveats=[
                "Prime federal contracts only - subcontracts and classified work are not in USAspending.",
                "Award amounts are total obligations as recorded by the awarding agency; timing is by federal fiscal year (Oct-Sep).",
                "Recipient matching is by exact normalized name ('Exponent' / 'Failure Analysis Associates'); awards under any other spelling are excluded rather than fuzzy-matched.",
                "Federal work is a small share of Exponent's revenue - this is a credibility/footprint indicator, not a revenue driver.",
            ],
            methodology_id="p5_federal_awards"),
        {"by_fiscal_year": [{"fy": fy, **by_fy[fy]} for fy in sorted(by_fy)],
         "by_agency": sorted(
             [{"agency": k, **v} for k, v in by_agency.items()],
             key=lambda r: -r["obligations"]),
         "top_awards": [{
             "award_id": a.get("Award ID"), "recipient": a.get("Recipient Name"),
             "amount": a.get("Award Amount"), "agency": a.get("Awarding Agency"),
             "sub_agency": a.get("Awarding Sub Agency"),
             "start": a.get("Start Date"), "end": a.get("End Date"),
             "description": (a.get("Description") or "")[:240],
             "fy": a["fiscal_year"]} for a in top_awards]},
    )
    log.info("P5 awards: %d matched awards", len(awards))


def _build_regulations(use_cache):
    end_year = date.today().year
    counts = regulations_gov.yearly_counts(REGS_START_YEAR, end_year, use_cache=use_cache)
    evidence = regulations_gov.evidence_sample(use_cache=use_cache)
    any_data = any(isinstance(r.get("documents"), dict) for r in counts)
    jsonio.write_site_json(
        "p5_regulatory_mentions.json",
        provenance.envelope(
            pipeline="p5_gov", output="regulatory_mentions",
            status="ok" if any_data else "unavailable",
            status_reason=None if any_data else "all count queries failed",
            sources=[provenance.source(
                "Regulations.gov v4 API (documents + comments full-text search)",
                "https://api.regulations.gov/v4/documents",
                fetched_at=_now(),
                records_matched=len(evidence))] if any_data else [],
            coverage={"start": str(REGS_START_YEAR), "end": str(end_year)},
            caveats=[
                "The 'strict' series counts quoted phrases that can only mean the firm ('Exponent, Inc', 'prepared by Exponent'); the 'raw' series counts the bare word 'Exponent', which includes unrelated math/finance uses - shown for transparency.",
                "Regulations.gov coverage differs by agency and era; early years underrepresent activity.",
                "A mention can be favorable (Exponent's own study submitted) or critical (an opposing comment citing Exponent's work) - the count alone does not distinguish; read the evidence table.",
                "Counts use the API's total-results field per calendar year; documents and comments are counted separately.",
                "Regulations.gov's own posting volume collapsed in 2025 (~65k documents vs several hundred thousand in typical years), so use the per-10k-documents normalized rate - not the raw count - when reading recent years.",
            ],
            methodology_id="p5_regulatory_mentions"),
        {"yearly": counts, "evidence": evidence[:200]} if any_data else None,
    )
    log.info("P5 regulations: %d years, %d evidence rows", len(counts), len(evidence))
