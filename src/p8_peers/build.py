"""P8 build: EXPO vs consulting peers on publications, financials, court footprint."""
import json
import logging
from datetime import date, datetime, timezone

from config import settings
from src.common import http, jsonio, provenance
from src.p8_peers import peers as P

log = logging.getLogger(__name__)

COURTS_START, PUBS_START = 2016, 2010


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(step=None, use_cache=True):
    end_year = date.today().year
    firms = []
    notes = []
    for peer in P.PEERS:
        firm = {"key": peer["key"], "name": peer["name"], "ticker": peer["ticker"]}
        # publications
        try:
            inst_id, err = P.resolve_institution(peer, use_cache=use_cache)
            if inst_id:
                pubs = P.publications_by_year(inst_id, use_cache=use_cache)
                firm["openalex_id"] = inst_id
                firm["publications"] = [{"year": y, "works": pubs[y]}
                                        for y in sorted(pubs) if y >= PUBS_START]
            else:
                # a consultancy with NO institution record has no research
                # footprint at all - that is a finding, not a data failure
                firm["publications"] = []
                firm["publications_note"] = ("not in the OpenAlex research index at all - "
                                             "no institutional publication footprint")
        except http.SourceUnavailable as exc:
            notes.append(f"{peer['key']} publications failed: {exc.reason}")
        # financials
        try:
            firm["financials"] = P.financials(peer["ticker"], use_cache=use_cache)
        except (http.SourceUnavailable, KeyError) as exc:
            notes.append(f"{peer['key']} financials failed: {exc}")
        firms.append(firm)

    # court footprint - quota-aware; may complete on a later run
    courts_status = "ok"
    if step in (None, "courts"):
        from src.p2_litigation.fetch import QuotaExhausted
        for firm, peer in zip(firms, P.PEERS):
            try:
                firm["courts"] = P.court_counts(peer, COURTS_START, end_year,
                                                use_cache=use_cache)
            except (QuotaExhausted, http.SourceUnavailable) as exc:
                courts_status = "partial"
                notes.append(f"{peer['key']} court counts stopped: {exc}; re-run to resume")
                break

    status = "ok" if courts_status == "ok" and not notes else "partial"
    jsonio.write_site_json(
        "p8_peers.json",
        provenance.envelope(
            pipeline="p8_peers", output="peers", status=status,
            status_reason="; ".join(notes) if notes else None,
            sources=[
                provenance.source("OpenAlex (publications per institution per year)",
                                  "https://api.openalex.org/works", fetched_at=_now()),
                provenance.source("SEC EDGAR XBRL companyfacts (revenue, operating income)",
                                  "https://data.sec.gov/api/xbrl/", fetched_at=_now()),
                provenance.source("CourtListener v4 search API (yearly counts)",
                                  "https://www.courtlistener.com/api/rest/v4/search/",
                                  fetched_at=_now()),
            ],
            coverage={"start": str(PUBS_START), "end": str(end_year)},
            caveats=[
                "Peers differ in size and mix: FTI (~$3.7B revenue) and ICF (~$2B) are far larger than Exponent (~$0.6B) and CRA (~$0.7B); compare TRENDS and margins, not absolute levels.",
                "Publications use each firm's OpenAlex institution record; firms that publish under subsidiary names may be undercounted.",
                "Court mentions use each firm's name near expert-witness language - the same method (and the same limitations) as the Exponent litigation chart.",
                "Operating margin is operating income / revenue from each company's own XBRL filings; consulting firms differ in what sits in operating costs, so small gaps are noise - the 2x+ gap is not.",
            ],
            methodology_id="p8_financials"),
        {"firms": firms},
    )
    log.info("P8: %d firms, status %s%s", len(firms), status,
             (" (" + "; ".join(notes) + ")") if notes else "")
