"""P11: how exposed is Exponent's bench to AI substitution?

There is no honest way to score "can a model do this job". Any such number would
be an opinion dressed as data, and this project does not ship those. So we ask
questions that primary sources CAN answer:

1. Does Exponent itself think AI threatens demand? Its 10-K risk factors are a
   legally-consequential statement of management's own view. We count AI mentions
   per annual report and quote the risk factor verbatim. A brand-new risk factor
   is a dated, falsifiable fact - not a vibe.
2. WHERE does Exponent say the exposure sits? Their own scoping sentence answers
   it, and we quote it rather than paraphrase.
3. What is the structural counter-argument, in numbers we already hold? Work that
   ends in sworn testimony needs a human who can be cross-examined (Rule 702), so
   we count the bench sitting in practices with documented courtroom presence.

Every output is either a count of something in a filing or a verbatim quote from
one. Nothing is scored, weighted or predicted.
"""
import logging
import re
from datetime import datetime, timezone

from src.common import http, jsonio, provenance
from src.p7_utilization import edgar_8k

log = logging.getLogger(__name__)

EXPO_CIK = 851520
YEARS_BACK = 6

_AI_TOKEN = re.compile(r"\bAI\b|artificial intelligence|machine learning", re.IGNORECASE)
# the risk-factor heading Exponent introduced in the FY2025 (filed 2026) 10-K
_DEMAND_RISK = re.compile(
    r"(Artificial intelligence \(AI\) technologies may reduce demand for our services"
    r".{0,1800}?)(?=Risks Related|Our adoption and use of artificial|$)",
    re.IGNORECASE | re.DOTALL)
_SCOPE_SENTENCE = re.compile(
    r"[^.]{0,300}more standardized in nature[^.]{0,120}\.", re.IGNORECASE)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _accession_url(accession):
    return (f"https://www.sec.gov/Archives/edgar/data/{EXPO_CIK}/"
            f"{accession.replace('-', '')}/{accession}-index.htm")


def _testimony_anchor():
    """Bench sitting in practices with documented courtroom presence.

    Uses only data already on the site: the live practice census (P1) and the
    practices we attributed named testifying experts to in federal opinions (P2).
    This is a LOWER BOUND - court records are sparse and consulting experts never
    appear in them at all.
    """
    try:
        roster = jsonio.read_site_json("p1_current_roster.json")
        daubert = jsonio.read_site_json("p2_daubert.json")
    except FileNotFoundError:
        return None
    by_practice = (roster.get("data") or {}).get("by_practice") or []
    total = sum(p["count"] for p in by_practice)
    court_practices = set((daubert.get("data") or {}).get("by_practice") or {})
    if not total or not court_practices:
        return None
    covered = [p for p in by_practice if p["practice"] in court_practices]
    n_covered = sum(p["count"] for p in covered)
    cases = (daubert.get("data") or {}).get("exponent", {}).get("cases") or []
    experts = {c.get("expert") for c in cases if c.get("expert")}
    return {
        "bench_total": total,
        "bench_in_courtroom_practices": n_covered,
        "share_pct": round(n_covered / total * 100, 1),
        "practices_with_court_presence": sorted(p["practice"] for p in covered),
        "named_experts_found": len(experts),
        "opinions_reviewed": len(cases),
    }


def run(step=None, use_cache=True):
    try:
        filings = edgar_8k.list_filings(EXPO_CIK, ("10-K",), use_cache=use_cache)[:YEARS_BACK]
    except http.SourceUnavailable as exc:
        jsonio.write_site_json(
            "p11_ai_exposure.json",
            provenance.envelope(
                pipeline="p11_ai_exposure", output="ai_exposure", status="unavailable",
                status_reason=f"SEC filing list unavailable: {exc.reason}",
                sources=[], coverage=None,
                caveats=["Nothing shown rather than a guess."],
                methodology_id="p11_ai_exposure"),
            None)
        return

    years, risk_factor, scope_sentence = [], None, None
    for filing in filings:
        text = edgar_8k.primary_doc_text(EXPO_CIK, filing, use_cache=use_cache)
        if not text:
            log.warning("10-K %s: no primary document text", filing["filed"])
            continue
        mentions = len(_AI_TOKEN.findall(text))
        m = _DEMAND_RISK.search(text)
        years.append({
            "filed": filing["filed"],
            "fiscal_year": int(filing["filed"][:4]) - 1,
            "ai_mentions": mentions,
            "has_ai_demand_risk_factor": bool(m),
            "accession": filing["accession"],
            "url": _accession_url(filing["accession"]),
        })
        if m and risk_factor is None:   # newest filing wins
            risk_factor = {"filed": filing["filed"], "accession": filing["accession"],
                           "url": _accession_url(filing["accession"]),
                           "verbatim": _clean(m.group(1))[:1500]}
            sm = _SCOPE_SENTENCE.search(m.group(1))
            if sm:
                scope_sentence = _clean(sm.group(0))

    years.sort(key=lambda r: r["fiscal_year"])
    if not years:
        jsonio.write_site_json(
            "p11_ai_exposure.json",
            provenance.envelope(
                pipeline="p11_ai_exposure", output="ai_exposure", status="unavailable",
                status_reason="no 10-K text could be read",
                sources=[], coverage=None,
                caveats=["Nothing shown rather than a guess."],
                methodology_id="p11_ai_exposure"),
            None)
        return

    first_flagged = next((r["fiscal_year"] for r in years
                          if r["has_ai_demand_risk_factor"]), None)
    anchor = _testimony_anchor()

    jsonio.write_site_json(
        "p11_ai_exposure.json",
        provenance.envelope(
            pipeline="p11_ai_exposure", output="ai_exposure",
            status="ok" if risk_factor else "partial",
            status_reason=None if risk_factor
            else "no AI demand risk factor located in any 10-K read",
            sources=[provenance.source(
                f"Exponent 10-K annual reports, {years[0]['filed']} to {years[-1]['filed']} (SEC EDGAR)",
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={EXPO_CIK}&type=10-K",
                fetched_at=_now(), records_scanned=len(years),
                records_matched=sum(1 for r in years if r["has_ai_demand_risk_factor"]))],
            coverage={"start": str(years[0]["fiscal_year"]), "end": str(years[-1]["fiscal_year"])},
            caveats=[
                "This does NOT score whether AI can do Exponent's work - no honest public dataset answers that, and a made-up score is exactly the kind of number this project refuses to print.",
                "It reports what the company itself told the SEC, where a false or misleading statement carries legal consequence: how often it discusses AI, and whether it flags AI as a demand risk.",
                "Counting mentions measures ATTENTION, not danger. A risk factor is a disclosure of what could go wrong, not a prediction that it will - companies add them defensively and lawyers write them broadly.",
                "The word count includes AI as an OPPORTUNITY (Exponent's own Data Sciences practice sells AI/ML work) and as an internal-use risk, not only as a threat. Read the quoted passages, not the bar height.",
                "The courtroom-bench figure is a LOWER BOUND: it counts practices we could tie to a named testifying expert in the federal opinions we sampled. Consulting experts never appear in court records, and state courts are sparsely covered, so the true testimony-anchored share is higher.",
            ],
            methodology_id="p11_ai_exposure"),
        {"years": years,
         "first_year_flagged": first_flagged,
         "risk_factor": risk_factor,
         "scope_sentence": scope_sentence,
         "testimony_anchor": anchor},
    )
    log.info("P11: %d 10-Ks | AI mentions %s | risk factor first flagged FY%s | anchor %s",
             len(years), [r["ai_mentions"] for r in years], first_flagged,
             anchor["share_pct"] if anchor else None)
