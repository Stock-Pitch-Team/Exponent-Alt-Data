"""Peer data acquisition: OpenAlex publications + EDGAR financials + CL court counts."""
import json
import logging

from config import settings
from src.common import edgar, http

log = logging.getLogger(__name__)

PEERS = [
    {"key": "EXPO", "name": "Exponent", "ticker": "EXPO",
     "openalex_search": "Exponent", "openalex_id": "I13383945",
     "cl_query": '("Exponent, Inc." OR "Exponent Inc.")'},
    {"key": "FCN", "name": "FTI Consulting", "ticker": "FCN",
     "openalex_search": "FTI Consulting",
     "cl_query": '"FTI Consulting"'},
    {"key": "CRAI", "name": "CRA International (Charles River Associates)", "ticker": "CRAI",
     "openalex_search": "Charles River Associates",
     "cl_query": '("Charles River Associates" OR "CRA International")'},
    {"key": "ICFI", "name": "ICF International", "ticker": "ICFI",
     "openalex_search": "ICF International",
     "cl_query": '"ICF International"'},
]

EXPERT_CONTEXT = '(expert OR witness OR testimony OR testified OR retained OR deposition OR "Rule 702" OR Daubert)'


def resolve_institution(peer: dict, use_cache=True):
    """Find the OpenAlex institution id for a peer (company type preferred)."""
    if peer.get("openalex_id"):
        return peer["openalex_id"], None
    raw = http.cached_get("https://api.openalex.org/institutions",
                          params={"search": peer["openalex_search"],
                                  "mailto": settings.CONTACT_EMAIL},
                          use_cache=use_cache)
    results = json.loads(raw).get("results", [])
    companies = [r for r in results if r.get("type") == "company"]
    pick = (companies or results or [None])[0]
    if not pick:
        return None, "no OpenAlex institution match"
    return pick["id"].rsplit("/", 1)[-1], None


def publications_by_year(institution_id: str, use_cache=True) -> dict:
    """{year: works} via a single group_by aggregation request."""
    raw = http.cached_get("https://api.openalex.org/works", params={
        "filter": f"authorships.institutions.id:{institution_id}",
        "group_by": "publication_year",
        "mailto": settings.CONTACT_EMAIL,
    }, use_cache=use_cache)
    groups = json.loads(raw).get("group_by", [])
    return {int(g["key"]): g["count"] for g in groups if str(g["key"]).isdigit()}


def financials(ticker: str, use_cache=True) -> dict:
    """Annual revenue + operating margin from EDGAR companyfacts."""
    cik = edgar.cik_for_ticker(ticker)
    facts = edgar.companyfacts(cik)
    _, rev = edgar.first_available_series(facts, [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues"], "annual")
    op = edgar.annual_series(facts, "OperatingIncomeLoss")
    op_by_year = {p["period"]: p["value"] for p in op}
    out = []
    for p in rev:
        year = p["period"]
        row = {"year": int(year), "revenue": p["value"]}
        if year in op_by_year and p["value"]:
            row["op_margin_pct"] = round(op_by_year[year] / p["value"] * 100, 1)
        out.append(row)
    for i, row in enumerate(out):
        prev = out[i - 1]["revenue"] if i else None
        row["rev_growth_pct"] = (round((row["revenue"] / prev - 1) * 100, 1)
                                 if prev else None)
    return {"cik": cik, "annual": out}


def court_counts(peer: dict, start_year: int, end_year: int, use_cache=True) -> dict:
    """Yearly CourtListener counts (opinions + RECAP) near expert language.
    Raises QuotaExhausted/SourceUnavailable upward - caller handles partial."""
    from src.p2_litigation import fetch
    q = f"{peer['cl_query']} AND {EXPERT_CONTEXT}"
    out = {}
    for year in range(start_year, end_year + 1):
        out[year] = {
            "opinions": fetch.count(q, "o", year),
            "recap": fetch.count(q, "r", year),
        }
    return out
