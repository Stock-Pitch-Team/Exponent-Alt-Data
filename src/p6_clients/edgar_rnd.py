"""R&D expense per revealed client (companyfacts) + market-wide baseline (frames).

Companies label research spending differently: most use the standard
us-gaap:ResearchAndDevelopmentExpense, but e.g. Amazon files 'Technology and
content / infrastructure' under its own tag. We search every namespace in the
company's facts for R&D-like tags and RECORD which line item was used - the
label travels with the number, nothing is silently substituted.
"""
import logging
import re

from src.common import edgar, http

log = logging.getLogger(__name__)

RND_TAG = "ResearchAndDevelopmentExpense"
_RND_LIKE = re.compile(
    r"^(ResearchAndDevelopmentExpense(ExcludingAcquiredInProcessCost)?|"
    r"ResearchAndDevelopment|ResearchDevelopmentAndEngineeringExpense|"
    r"TechnologyAndContentExpense|TechnologyAndInfrastructureExpense|"
    r"TechnologyAndDevelopmentExpense|ProductDevelopmentExpense)$")


def _best_rnd_series(facts: dict, start_year: int):
    """Find the R&D-like tag with the best annual coverage across namespaces.
    Returns (series, tag, namespace) or ([], None, None)."""
    standard = edgar.annual_series(facts, RND_TAG)
    if standard:
        return standard, RND_TAG, "us-gaap"
    best = ([], None, None)
    for ns, tags in (facts.get("facts") or {}).items():
        if ns == "dei":
            continue
        for tag in tags:
            if not _RND_LIKE.match(tag):
                continue
            series = edgar.annual_series(facts, tag, namespace=ns)
            recent = [p for p in series if int(p["period"]) >= start_year]
            if len(recent) > len([p for p in best[0] if int(p["period"]) >= start_year]):
                best = (series, tag, ns)
    return best


def client_series(matched: list[dict], start_year: int = 2012) -> list[dict]:
    out = []
    for client in matched:
        try:
            facts = edgar.companyfacts(int(client["cik"]))
        except http.SourceUnavailable as exc:
            out.append({**client, "rnd_annual": None,
                        "rnd_note": f"EDGAR fetch failed: {exc.reason}"})
            continue
        series, tag, ns = _best_rnd_series(facts, start_year)
        series = [p for p in series if int(p["period"]) >= start_year]
        out.append({**client,
                    "rnd_annual": [{"year": int(p["period"]), "value": p["value"]}
                                   for p in series] or None,
                    "rnd_tag": tag,
                    "rnd_is_standard": tag == RND_TAG,
                    "rnd_note": None if series else
                    "no R&D-like line item in this company's structured filings"})
    return out


def market_baseline(start_year: int, end_year: int) -> list[dict]:
    """Sum of reported R&D across ALL SEC filers per calendar year (XBRL frames)."""
    out = []
    for year in range(start_year, end_year + 1):
        try:
            doc = edgar.frames(RND_TAG, f"CY{year}")
        except http.SourceUnavailable as exc:
            log.warning("frames CY%d failed: %s", year, exc)
            out.append({"year": year, "total": None, "filers": None})
            continue
        rows = doc.get("data", [])
        out.append({"year": year,
                    "total": sum(r.get("val") or 0 for r in rows),
                    "filers": len(rows)})
    return out
