"""P4 build: fetch OpenAlex data, write p4_*.json site outputs."""
import json
import logging
from datetime import datetime, timezone

from config import entities, settings
from src.common import http, jsonio, provenance
from src.p4_moat import graph, openalex

log = logging.getLogger(__name__)

OPENALEX_URL = f"https://api.openalex.org/works?filter=authorships.institutions.id:{entities.OPENALEX_INSTITUTION_ID}"

CAVEATS_WORKS = [
    "Publications lag the underlying work by roughly 1-2 years (research is written up and peer-reviewed after it happens).",
    "Confidential consulting engagements rarely produce co-authored papers, so this measures Exponent's public scientific footprint - a moat indicator, not total business activity.",
    "OpenAlex assigns institutions by parsing author affiliation text; a small share of affiliations are mis-parsed or missing.",
    "Recent years (especially the last 1-2) are incomplete because indexing of new publications is still catching up.",
]


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(step=None, use_cache=True):
    try:
        works = openalex.fetch_works(use_cache=use_cache)
    except http.SourceUnavailable as exc:
        _write_unavailable(str(exc))
        return
    fetched_at = _now()

    # --- publications time series ---
    series = graph.publications_by_year(works)
    coverage = {"start": str(series[0]["year"]), "end": str(series[-1]["year"])} if series else None
    jsonio.write_site_json(
        "p4_publications_timeseries.json",
        provenance.envelope(
            pipeline="p4_moat", output="publications_timeseries", status="ok",
            sources=[provenance.source(
                "OpenAlex (institution I13383945, alias 'Failure Analysis Associates')",
                OPENALEX_URL, fetched_at=fetched_at,
                records_scanned=len(works), records_matched=len(works))],
            coverage=coverage, caveats=CAVEATS_WORKS,
            methodology_id="p4_publications"),
        {"series": series, "total_works": len(works)},
    )

    # --- citations RECEIVED per calendar year (live relevance, not vintage) ---
    cites = graph.citations_received_by_year(works)
    cseries = cites["series"]
    this_year = datetime.now(timezone.utc).year
    jsonio.write_site_json(
        "p4_citations_received.json",
        provenance.envelope(
            pipeline="p4_moat", output="citations_received", status="ok",
            sources=[provenance.source(
                "OpenAlex per-year citation counts (counts_by_year) across all Exponent-affiliated works",
                OPENALEX_URL, fetched_at=fetched_at,
                records_scanned=len(works),
                records_matched=sum(1 for w in works if w.get("counts_by_year")))],
            coverage={"start": str(cseries[0]["year"]), "end": str(cseries[-1]["year"])}
            if cseries else None,
            caveats=[
                "This counts citations RECEIVED in each calendar year by Exponent's entire body of work - the question 'how much is Exponent's science being used right now', which is different from the publication-count chart above.",
                "It is deliberately NOT citations-by-publication-year. That version punishes recent papers for not having existed long enough to be cited, and would show a fake collapse in the newest years.",
                f"The series starts in {cseries[0]['year'] if cseries else 'n/a'} because OpenAlex only publishes per-year citation counts for a rolling recent window - it is not a claim that nobody cited Exponent before then. Papers of every vintage, back to 1967, contribute to these bars.",
                f"{this_year} is a partial year - it counts citations logged so far, not a full twelve months. Read it as incomplete, never as a drop.",
                "OpenAlex's citation graph is itself still indexing recent literature, so the last 1-2 years drift upward after publication.",
                "The 'recent work' lines isolate citations earned by papers published within the last 5 and 10 years, separating a coasting back catalogue from current output that is landing.",
            ],
            methodology_id="p4_citations_received"),
        cites,
    )

    # --- corporate collaboration graph ---
    per_company, per_work = graph.corporate_partners(works)
    companies = sorted(per_company.values(), key=lambda c: -c["works"])
    nodes = [{"id": "exponent", "name": "Exponent, Inc.", "works": len(works),
              "is_exponent": True}]
    edges = []
    for c in companies:
        nodes.append({"id": c["id"], "name": c["name"], "works": c["works"],
                      "first_year": c["first_year"], "last_year": c["last_year"],
                      "top_topics": c["top_topics"], "is_exponent": False})
        edges.append({"source": "exponent", "target": c["id"], "weight": c["works"]})
    jsonio.write_site_json(
        "p4_collab_graph.json",
        provenance.envelope(
            pipeline="p4_moat", output="collab_graph", status="ok",
            sources=[provenance.source(
                "OpenAlex co-author institutions (type=company)",
                OPENALEX_URL, fetched_at=fetched_at,
                records_scanned=len(works), records_matched=len(per_work))],
            coverage=coverage, caveats=CAVEATS_WORKS + [
                "Only co-authors whose affiliation is typed as a company in OpenAlex are counted; universities, hospitals and government labs are excluded on purpose.",
            ],
            methodology_id="p4_collab_graph"),
        {"nodes": nodes, "edges": edges,
         "coauthored_works_sample": sorted(per_work, key=lambda w: -(w["cited_by"]))[:50]},
    )

    # --- rolling unique partners ---
    rolling = graph.rolling_unique_partners(per_work, window=3)
    jsonio.write_site_json(
        "p4_partners_rolling.json",
        provenance.envelope(
            pipeline="p4_moat", output="partners_rolling", status="ok",
            sources=[provenance.source(
                "OpenAlex co-author institutions (type=company)",
                OPENALEX_URL, fetched_at=fetched_at,
                records_scanned=len(works), records_matched=len(per_work))],
            coverage=coverage, caveats=CAVEATS_WORKS,
            methodology_id="p4_partners_rolling"),
        {"window_years": 3, "series": rolling},
    )

    # --- interim: partner list for P6 ---
    interim = settings.INTERIM_DIR / "p4_partners.json"
    interim.write_text(json.dumps(
        [{"name": c["name"], "openalex_id": c["id"], "works": c["works"],
          "first_year": c["first_year"], "last_year": c["last_year"]}
         for c in companies], indent=1), encoding="utf-8")

    # --- authors / talent ---
    try:
        authors = openalex.fetch_authors(use_cache=use_cache)
    except http.SourceUnavailable as exc:
        log.warning("authors fetch failed: %s", exc)
        authors = None
    if authors is not None:
        current = [a for a in authors
                   if any((i.get("id") == graph.EXPONENT_ID_URL)
                          for i in (a.get("last_known_institutions") or []))]
        top = sorted(authors, key=lambda a: -(a.get("cited_by_count") or 0))[:25]
        jsonio.write_site_json(
            "p4_authors.json",
            provenance.envelope(
                pipeline="p4_moat", output="authors", status="ok",
                sources=[provenance.source(
                    "OpenAlex authors affiliated with Exponent",
                    f"https://api.openalex.org/authors?filter=affiliations.institution.id:{entities.OPENALEX_INSTITUTION_ID}",
                    fetched_at=_now(), records_scanned=len(authors))],
                coverage=None,
                caveats=[
                    "Includes everyone who EVER published with an Exponent affiliation, including alumni; 'currently at Exponent' uses OpenAlex's last-known institution, which can be stale.",
                    "Citation counts measure scientific influence, not consulting revenue.",
                ],
                methodology_id="p4_authors"),
            {"total_ever_affiliated": len(authors),
             "currently_at_exponent": len(current),
             "top_authors": [{"name": a.get("display_name"),
                              "works": a.get("works_count"),
                              "citations": a.get("cited_by_count"),
                              "h_index": (a.get("summary_stats") or {}).get("h_index"),
                              "current": a in current} for a in top]},
        )
    log.info("P4 complete: %d works, %d corporate partners", len(works), len(companies))


def _write_unavailable(reason: str):
    for fname, output in [("p4_publications_timeseries.json", "publications_timeseries"),
                          ("p4_collab_graph.json", "collab_graph"),
                          ("p4_partners_rolling.json", "partners_rolling"),
                          ("p4_authors.json", "authors")]:
        jsonio.write_site_json(
            fname,
            provenance.envelope(
                pipeline="p4_moat", output=output, status="unavailable",
                status_reason=f"OpenAlex fetch failed: {reason}", sources=[],
                coverage=None, caveats=["No data was fetched; nothing is shown rather than showing fabricated data."],
                methodology_id="p4_unavailable"),
            None,
        )
