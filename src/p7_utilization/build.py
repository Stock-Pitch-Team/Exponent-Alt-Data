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
            metrics = edgar_8k.parse_metrics(text, allow_fte=True)
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
        text = edgar_8k.primary_doc_text(cik, filing, use_cache=use_cache)
        if "utilization" not in text.lower():
            continue
        scanned += 1
        # 10-Q/10-K states firmwide AND segment FTEs; the in-band document-wide
        # max is the firmwide figure (it always exceeds any segment's)
        metrics = edgar_8k.parse_metrics(text, allow_fte=True)
        if not metrics:
            continue
        slot = by_quarter.setdefault(quarter, {"quarter": quarter})
        if "accession" not in slot:
            slot.update({"accession": filing["accession"], "filed": filing["filed"],
                         "source_form": filing["form"]})
        for k, v in metrics.items():   # 8-K press-release values win
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
    _build_realized_rate(series)


AVAILABLE_HOURS_PER_QUARTER = 2080 / 4  # standard 40h week x 13 weeks


def _build_realized_rate(series):
    """Estimated blended realized rate = revenue / (FTE x utilization x hours).

    The LEVEL depends on the available-hours convention, so the trend is the
    signal; every input is a company-reported figure."""
    try:
        fin = jsonio.read_site_json("p6_expo_financials.json")
        revenue = {p["period"]: p["value"]
                   for p in fin["data"]["revenue_quarterly"]}
    except (FileNotFoundError, KeyError, TypeError):
        jsonio.write_site_json(
            "p7_realized_rate.json",
            provenance.envelope(
                pipeline="p7_utilization", output="realized_rate", status="unavailable",
                status_reason="EXPO revenue dataset not built yet (run p6 first)",
                sources=[], coverage=None,
                caveats=["No data; nothing shown rather than fabricated data."],
                methodology_id="p7_realized_rate"),
            None)
        return

    rows = []
    for r in series:
        q = r["quarter"]
        if q not in revenue or not r.get("utilization") or not r.get("fte"):
            continue
        hours = r["fte"] * (r["utilization"] / 100.0) * AVAILABLE_HOURS_PER_QUARTER
        rows.append({"quarter": q, "revenue": revenue[q], "fte": r["fte"],
                     "utilization": r["utilization"],
                     "billable_hours_est": round(hours),
                     "rate_est": round(revenue[q] / hours, 2)})
    for i, row in enumerate(rows):
        prior = next((p for p in rows[:i] if
                      p["quarter"] == f"{int(row['quarter'][:4]) - 1}{row['quarter'][4:]}"),
                     None)
        row["rate_yoy_pct"] = (round((row["rate_est"] / prior["rate_est"] - 1) * 100, 1)
                               if prior else None)

    jsonio.write_site_json(
        "p7_realized_rate.json",
        provenance.envelope(
            pipeline="p7_utilization", output="realized_rate",
            status="ok" if len(rows) >= 8 else "partial",
            status_reason=None if len(rows) >= 8 else f"only {len(rows)} joinable quarters",
            sources=[provenance.source(
                "Derived: SEC-reported revenue / (company-stated FTE x utilization x 520h)",
                "https://data.sec.gov/", fetched_at=_now(), records_matched=len(rows))],
            coverage={"start": rows[0]["quarter"], "end": rows[-1]["quarter"]} if rows else None,
            caveats=[
                "Every input is company-reported (revenue from XBRL, utilization and FTE from filed text); only the division is ours.",
                "The dollar LEVEL depends on the 40h/week available-hours convention and on revenue including ~5-6% pass-through reimbursements - read the TREND and the YoY, not the exact level.",
                "Quarters missing a stated utilization or FTE are absent, never interpolated.",
            ],
            methodology_id="p7_realized_rate"),
        {"series": rows},
    )
    log.info("P7 realized rate: %d quarters", len(rows))


def _unavailable(reason):
    jsonio.write_site_json(
        "p7_utilization.json",
        provenance.envelope(
            pipeline="p7_utilization", output="utilization", status="unavailable",
            status_reason=reason, sources=[], coverage=None,
            caveats=["No data fetched; nothing shown rather than fabricated data."],
            methodology_id="p7_utilization"),
        None)
