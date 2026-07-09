"""P6 build: revealed-client R&D tracker + EXPO financials."""
import logging
from datetime import date, datetime, timezone

from src.common import jsonio, provenance
from src.p6_clients import client_list, edgar_rnd, expo_financials, ticker_map

log = logging.getLogger(__name__)

START_YEAR = 2018  # short-term thesis: recent growth windows, not decade-old baselines


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(step=None, use_cache=True):
    if step in (None, "expo"):
        expo_financials.run(use_cache=use_cache)
    if step in (None, "clients"):
        _build_clients(use_cache)


def _build_clients(use_cache):
    end_year = date.today().year - 1  # last complete filing year
    clients = client_list.combined()
    has_parties = any(c["relationship"] == "associated_party" for c in clients)
    matched, unmatched = ticker_map.build_map(clients)
    with_rnd = edgar_rnd.client_series(matched, start_year=START_YEAR)

    # constant-sample aggregate: only companies reporting the STANDARD R&D tag
    # in EVERY year (alternate line items like Amazon's technology-and-content
    # are shown per-company but excluded here - different definitions don't sum)
    years = list(range(START_YEAR, end_year + 1))
    constant = [c for c in with_rnd if c["rnd_annual"] and c.get("rnd_is_standard")
                and {p["year"] for p in c["rnd_annual"]}.issuperset(years)]
    agg = []
    for y in years:
        total = sum(next(p["value"] for p in c["rnd_annual"] if p["year"] == y)
                    for c in constant)
        agg.append({"year": y, "total_rnd": total, "companies": len(constant)})
    for i, row in enumerate(agg):
        row["yoy_pct"] = (round((row["total_rnd"] / agg[i-1]["total_rnd"] - 1) * 100, 1)
                          if i > 0 and agg[i-1]["total_rnd"] else None)

    baseline = edgar_rnd.market_baseline(START_YEAR, end_year)
    for i, row in enumerate(baseline):
        prev = baseline[i-1]["total"] if i > 0 else None
        row["yoy_pct"] = (round((row["total"] / prev - 1) * 100, 1)
                          if row["total"] and prev else None)

    n_reporting = sum(1 for c in with_rnd if c["rnd_annual"])
    status = "ok" if n_reporting >= 10 else "partial"
    jsonio.write_site_json(
        "p6_client_rnd.json",
        provenance.envelope(
            pipeline="p6_clients", output="client_rnd", status=status,
            status_reason=None if status == "ok" else
            f"only {n_reporting} revealed clients report R&D so far"
            + ("" if has_parties else " (litigation parties pending P2 completion)"),
            sources=[
                provenance.source(
                    "Revealed clients: OpenAlex co-authorships (P4) + court-case parties (P2)",
                    "derived", note=f"{len(clients)} candidate names, "
                    f"{len(matched)} matched to SEC filers, {len(unmatched)} unmatched/ambiguous"),
                provenance.source(
                    "SEC EDGAR XBRL companyfacts + frames (us-gaap:ResearchAndDevelopmentExpense)",
                    "https://data.sec.gov/api/xbrl/", fetched_at=_now()),
            ],
            coverage={"start": str(START_YEAR), "end": str(end_year)},
            caveats=[
                "Exponent discloses NO client list. This 'revealed client' sample comes from public co-authored research and court cases - a lower bound, biased toward clients who publish or litigate.",
                "'research_partner' = co-authored publications with Exponent (high confidence there is a relationship). 'associated_party' = was a party in a case where Exponent appears near expert language - the side that hired Exponent is usually unknown.",
                "The aggregate uses only the constant sample of companies reporting R&D in every year shown, so growth is not distorted by companies entering/leaving the sample.",
                "R&D values are exactly as reported to the SEC. Companies that file research spending under a different line item (e.g. Amazon's 'technology and content/infrastructure') show that item, clearly labeled; only standard-definition R&D goes into the aggregate line, and companies with no R&D-like line item at all are marked n/a, never estimated.",
                "Logic being tested: rising client/sector R&D budgets -> more proactive consulting demand for Exponent. This is a demand-environment indicator, not a revenue forecast.",
            ],
            methodology_id="p6_client_rnd"),
        {"clients": with_rnd, "unmatched": unmatched[:60],
         "constant_sample_aggregate": agg,
         "market_baseline": baseline},
    )
    log.info("P6: %d clients (%d with R&D), constant sample %d",
             len(with_rnd), n_reporting, len(constant))
