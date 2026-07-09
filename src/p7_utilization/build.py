"""P7 build: official quarterly utilization % and technical FTEs from EXPO 8-Ks."""
import logging
from datetime import datetime, timezone

from config import entities
from src.common import edgar, http, jsonio, provenance, quarters

from src.p7_utilization import edgar_8k

log = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(step=None, use_cache=True):
    try:
        cik = edgar.cik_for_ticker(entities.EXPO_TICKER)
        filings = edgar_8k.list_8k_filings(cik, use_cache=use_cache)
    except (http.SourceUnavailable, KeyError) as exc:
        _unavailable(f"EDGAR fetch failed: {exc}")
        return

    by_quarter: dict = {}
    scanned = 0
    for filing in filings:
        try:
            texts = edgar_8k.exhibit_texts(cik, filing["accession"], use_cache=use_cache)
        except http.SourceUnavailable as exc:
            log.warning("filing %s failed: %s", filing["accession"], exc)
            continue
        for text in texts:
            if "utilization" not in text.lower():
                continue
            scanned += 1
            metrics = edgar_8k.parse_metrics(text)
            if not metrics:
                continue
            quarter = edgar_8k.quarter_from_text_or_date(
                text, filing.get("report_date"), filing["filed"])
            if not quarter:
                continue
            slot = by_quarter.setdefault(quarter, {"quarter": quarter,
                                                   "accession": filing["accession"],
                                                   "filed": filing["filed"]})
            # first (most exhibit-like) document wins; don't overwrite with later dups
            for k, v in metrics.items():
                slot.setdefault(k, v)
            break

    # fill gaps from 10-Q / 10-K MD&A (8-K press-release values win).
    # EXPO's fiscal quarters end the Friday nearest the calendar quarter-end,
    # sometimes a few days INTO the next quarter - shift back 7 days to bucket.
    from datetime import date as _date, timedelta as _td
    for filing in edgar_8k.list_filings(cik, ("10-Q", "10-K"), use_cache=use_cache):
        rd = filing.get("report_date")
        if not rd:
            continue
        d = _date.fromisoformat(rd) - _td(days=7)
        quarter = f"{d.year}-Q{(d.month - 1) // 3 + 1}"
        if quarter in by_quarter and "utilization" in by_quarter[quarter]:
            continue
        text = edgar_8k.primary_doc_text(cik, filing, use_cache=use_cache)
        if "utilization" not in text.lower():
            continue
        scanned += 1
        metrics = edgar_8k.parse_metrics(text)
        if not metrics.get("utilization"):
            continue
        slot = by_quarter.setdefault(quarter, {"quarter": quarter})
        slot.update({"accession": filing["accession"], "filed": filing["filed"],
                     "source_form": filing["form"]})
        for k, v in metrics.items():
            slot.setdefault(k, v)

    series = [by_quarter[q] for q in sorted(by_quarter, key=quarters.sort_key)]
    with_util = [r for r in series if "utilization" in r]
    status = "ok" if len(with_util) >= 8 else ("partial" if with_util else "unavailable")
    jsonio.write_site_json(
        "p7_utilization.json",
        provenance.envelope(
            pipeline="p7_utilization", output="utilization", status=status,
            status_reason=None if status == "ok" else f"only {len(with_util)} quarters parsed",
            sources=[provenance.source(
                "Exponent 8-K earnings-release exhibits (SEC EDGAR)",
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K",
                fetched_at=_now(), records_scanned=scanned,
                records_matched=len(with_util))],
            coverage={"start": series[0]["quarter"], "end": series[-1]["quarter"]}
            if series else None,
            caveats=[
                "Utilization and technical-FTE figures are read directly from the text of Exponent's own filed earnings press releases - the same numbers management quotes on earnings calls.",
                "Parsed by pattern-matching the release text; quarters where the wording defeated the parser are simply absent, never estimated. Each point carries its SEC accession number.",
                "Utilization here is Exponent's own definition (billable hours as a share of total available hours), which the thesis triggers are written against: mid-to-high-70s = bull confirmation, stalling at ~73% = bear signal.",
            ],
            methodology_id="p7_utilization"),
        {"series": series},
    )
    log.info("P7: %d quarters with utilization, %d with FTE (scanned %d releases)",
             len(with_util), sum(1 for r in series if "fte" in r), scanned)


def _unavailable(reason):
    jsonio.write_site_json(
        "p7_utilization.json",
        provenance.envelope(
            pipeline="p7_utilization", output="utilization", status="unavailable",
            status_reason=reason, sources=[], coverage=None,
            caveats=["No data fetched; nothing shown rather than fabricated data."],
            methodology_id="p7_utilization"),
        None)
