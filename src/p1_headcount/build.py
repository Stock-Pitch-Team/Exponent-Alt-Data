"""P1 build: headcount time series (Wayback proxy), live roster, job postings."""
import json
import logging
from collections import Counter
from datetime import date, datetime, timezone

from config import settings
from src.common import http, jsonio, provenance
from src.p1_headcount import careers, cdx, live_roster

log = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(step=None, use_cache=True):
    if step in (None, "roster"):
        _build_roster(use_cache)
    if step in (None, "timeseries"):
        _build_timeseries(use_cache)
    if step in (None, "careers"):
        _build_careers(use_cache)


def _build_roster(use_cache):
    try:
        roster = live_roster.fetch_roster(use_cache=use_cache)
    except http.SourceUnavailable as exc:
        jsonio.write_site_json(
            "p1_current_roster.json",
            provenance.envelope(
                pipeline="p1_headcount", output="current_roster", status="unavailable",
                status_reason=str(exc), sources=[], coverage=None,
                caveats=["No data fetched; nothing shown rather than fabricated data."],
                methodology_id="p1_current_roster"),
            None)
        return

    people = roster["people"]
    by_practice = Counter(p["practice"] or "Unlisted" for p in people)
    by_band = Counter(p["band"] for p in people)
    title_coverage = sum(1 for p in people if p["title_guess"]) / len(people) if people else 0
    jsonio.write_site_json(
        "p1_current_roster.json",
        provenance.envelope(
            pipeline="p1_headcount", output="current_roster", status="ok",
            sources=[provenance.source(
                "Exponent.com people directory (site's own public search index)",
                roster["source_url"], fetched_at=_now(),
                records_matched=len(people),
                note=f"index reports {roster['total_hits']} professionals")],
            coverage=None,
            caveats=[
                "This is the PUBLIC consultant directory; Exponent's 10-K FTE count also includes staff without profile pages, so levels differ from reported headcount (trends are comparable).",
                f"Seniority bands are parsed from bio text and cover only {title_coverage:.0%} of profiles; 'unknown' is shown for the rest, not guessed.",
                "Practice-area labels are Exponent's own site categories.",
            ],
            methodology_id="p1_current_roster"),
        {"total": len(people),
         "by_practice": [{"practice": k, "count": v}
                         for k, v in by_practice.most_common()],
         "by_band": [{"band": k, "count": v} for k, v in by_band.most_common()],
         "people": people},
    )
    # entity dictionary for P2 expert matching
    (settings.INTERIM_DIR / "p1_roster_names.json").write_text(
        json.dumps(sorted(p["name"] for p in people if p["name"]), indent=0),
        encoding="utf-8")
    log.info("P1 roster: %d people, %d practices", len(people), len(by_practice))


def _build_timeseries(use_cache):
    current_year = date.today().year
    try:
        eras = cdx.census(use_cache=use_cache)
    except http.SourceUnavailable as exc:
        jsonio.write_site_json(
            "p1_headcount_timeseries.json",
            provenance.envelope(
                pipeline="p1_headcount", output="headcount_timeseries",
                status="unavailable", status_reason=str(exc), sources=[],
                coverage=None,
                caveats=["Wayback Machine CDX API unreachable; nothing shown rather than fabricated data."],
                methodology_id="p1_headcount_timeseries"),
            None)
        return

    series = cdx.yearly_series(eras, current_year)
    flows = cdx.joiners_leavers(eras, current_year)
    total_slugs = sum(len(s) for s in eras.values())
    # historical roster names for P2 (legacy era slugs are last-first)
    (settings.INTERIM_DIR / "p1_historical_slugs.json").write_text(
        json.dumps({era: sorted(slugs) for era, slugs in eras.items()}, indent=0),
        encoding="utf-8")
    jsonio.write_site_json(
        "p1_headcount_timeseries.json",
        provenance.envelope(
            pipeline="p1_headcount", output="headcount_timeseries", status="ok",
            sources=[provenance.source(
                "Internet Archive Wayback Machine CDX index (exponent.com profile URLs)",
                cdx.CDX_URL, fetched_at=_now(), records_matched=total_slugs,
                note="eras: " + ", ".join(f"{k}={len(v)} slugs" for k, v in eras.items()))],
            coverage={"start": "2004", "end": str(current_year)},
            caveats=[
                "METHOD: a consultant profile URL is counted as 'active' in every year between its first and last appearance in the Internet Archive - a PROXY for tenure, not an official roster.",
                "The Archive does not crawl every page every year, so absolute levels UNDERCOUNT true headcount, especially in early years and around the 2022-2023 site redesign (URL scheme changed).",
                "Method flag: every point in this series is 'url_count_proxy'. Trends and turning points are meaningful; exact levels are not.",
                "The last year's 'disappeared_profiles' is meaningless by construction (every URL's lifetime ends at the most recent crawl).",
                "The 2022-2023 spikes in new/disappeared profiles are the site redesign (every consultant's URL changed scheme), NOT real hiring or attrition; read flows only within one era.",
                "Cross-check: the current-year proxy can be compared against the live directory count and the FTE count in Exponent's 10-K.",
            ],
            methodology_id="p1_headcount_timeseries"),
        {"series": series, "flows": flows, "method": "url_count_proxy",
         "era_sizes": {k: len(v) for k, v in eras.items()}},
    )
    log.info("P1 timeseries: %d slugs across %d eras", total_slugs, len(eras))


def _build_careers(use_cache):
    try:
        result = careers.fetch_postings(use_cache=use_cache)
        status = "ok" if result.get("postings") else "partial"
        reason = None if result.get("postings") else result.get("note", "no postings found")
    except http.SourceUnavailable as exc:
        result, status, reason = None, "unavailable", str(exc)
    jsonio.write_site_json(
        "p1_job_postings.json",
        provenance.envelope(
            pipeline="p1_headcount", output="job_postings", status=status,
            status_reason=reason,
            sources=[provenance.source(
                "Exponent.com careers content (site's own public search index)",
                "https://www.exponent.com/careers", fetched_at=_now(),
                records_matched=len(result["postings"]) if result else 0)] if result else [],
            coverage=None,
            caveats=[
                "Snapshot of postings visible on the site at fetch time; no historical backfill is possible from this source, so the hiring series accumulates from today forward.",
                "Postings signal hiring INTENT by discipline; they are not hires.",
            ],
            methodology_id="p1_job_postings"),
        result,
    )
    log.info("P1 careers: %s", status)
