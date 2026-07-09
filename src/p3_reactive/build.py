"""P3 build: combine NHTSA / CPSC / openFDA into the quarterly Reactive Demand Index.

Blending method (disclosed verbatim in the explainer): each source's weighted
quarterly series is indexed to its own 2012-2019 average (=100), then the
blended index is the simple mean of available source indices. This prevents
high-volume sources (MAUDE reports) from drowning out low-volume ones (recalls).
No smoothing, no interpolation; missing quarters stay missing.
"""
import logging
from datetime import date, datetime, timezone

from config import settings
from config.categories import CATEGORY_KEYWORDS, SEVERITY_WEIGHTS
from src.common import http, jsonio, provenance, quarters
from src.p3_reactive import cpsc, nhtsa, openfda

log = logging.getLogger(__name__)

START_YEAR = 2010
BASE_START, BASE_END = 2012, 2019  # normalization base period


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _current_quarter():
    """Last COMPLETE quarter — the in-progress quarter would be a misleading partial point."""
    today = date.today()
    year, q = today.year, (today.month - 1) // 3 + 1
    if q == 1:
        return year - 1, 4
    return year, q - 1


def _quarter_labels():
    end_year, end_q = _current_quarter()
    return [q for q, _, _ in quarters.quarter_range(START_YEAR, end_year, end_q)]


def _agg_to_series(agg: dict, labels: list[str]) -> dict:
    """{(quarter, cat): {count, weighted}} -> per-quarter totals + per-category."""
    out = {}
    for label in labels:
        cats = {}
        total_count, total_weighted = 0, 0.0
        for cat in CATEGORY_KEYWORDS:
            slot = agg.get((label, cat))
            if slot:
                cats[cat] = slot
                total_count += slot["count"]
                total_weighted += slot["weighted"]
        out[label] = {"count": total_count, "weighted": total_weighted,
                      "categories": cats}
    return out


def _index_to_base(series: dict, labels: list[str]) -> dict:
    base_vals = [series[q]["weighted"] for q in labels
                 if BASE_START <= int(q[:4]) <= BASE_END and q in series]
    base = sum(base_vals) / len(base_vals) if base_vals else None
    if not base:
        return {}
    return {q: round(series[q]["weighted"] / base * 100, 1)
            for q in labels if q in series}


def run(step=None, use_cache=True):
    labels = _quarter_labels()
    end_year, end_q = _current_quarter()
    sources_meta, caveats_extra = [], []
    per_source_series = {}

    # --- NHTSA flat files (must already be downloaded to data/raw/nhtsa/) ---
    rcl_path = settings.RAW_DIR / "nhtsa" / "FLAT_RCL_POST_2010.zip"
    cmpl_path = settings.RAW_DIR / "nhtsa" / "FLAT_CMPL.zip"
    for path, url, parser, key in [
        (rcl_path, nhtsa.RECALLS_URL, nhtsa.parse_recalls, "nhtsa_recalls"),
        (cmpl_path, nhtsa.COMPLAINTS_URL, nhtsa.parse_complaints, "nhtsa_complaints"),
    ]:
        if not path.exists():
            try:
                log.info("downloading %s ...", url)
                http.download_file(url, path, expected_min_bytes=1 << 20)
            except http.SourceUnavailable as exc:
                caveats_extra.append(f"{key} unavailable: {exc.reason}")
                continue
        agg, scanned, matched = parser(path)
        per_source_series[key] = _agg_to_series(agg, labels)
        sources_meta.append(provenance.source(
            f"NHTSA ODI flat file ({key})", url, fetched_at=_now(),
            records_scanned=scanned, records_matched=matched))

    # --- CPSC ---
    try:
        recalls = cpsc.fetch_recalls(START_YEAR, end_year, use_cache=use_cache)
        classified = cpsc.classify(recalls)
        agg = {}
        for rec in classified:
            q = quarters.to_quarter(rec["date"])
            for cat in rec["categories"]:
                slot = agg.setdefault((q, cat), {"count": 0, "weighted": 0.0})
                slot["count"] += 1
                slot["weighted"] += rec["weight"]
        per_source_series["cpsc_recalls"] = _agg_to_series(agg, labels)
        sources_meta.append(provenance.source(
            "CPSC recall database (saferproducts.gov REST API)", cpsc.BASE,
            fetched_at=_now(), records_scanned=len(recalls),
            records_matched=len(classified)))
    except http.SourceUnavailable as exc:
        caveats_extra.append(f"CPSC recalls unavailable: {exc.reason}")

    # --- openFDA (medical_device category by definition) ---
    qtuples = list(quarters.quarter_range(START_YEAR, end_year, end_q))
    fda_recalls = openfda.recalls_by_quarter(qtuples, use_cache=use_cache)
    if any("counts" in r for r in fda_recalls):
        per_source_series["fda_device_recalls"] = {
            r["quarter"]: {"count": r["total"], "weighted": r["weighted"],
                           "categories": {"medical_device": {"count": r["total"],
                                                             "weighted": r["weighted"]}}}
            for r in fda_recalls if "counts" in r}
        sources_meta.append(provenance.source(
            "openFDA device enforcement (recalls by classification)",
            openfda.ENFORCEMENT, fetched_at=_now(),
            records_scanned=sum(r.get("total", 0) for r in fda_recalls)))
    maude = openfda.maude_by_quarter(qtuples, use_cache=use_cache)
    if any("counts" in r for r in maude):
        per_source_series["fda_maude_events"] = {
            r["quarter"]: {"count": r["total"], "weighted": r["weighted"],
                           "categories": {"medical_device": {"count": r["total"],
                                                             "weighted": r["weighted"]}}}
            for r in maude if "counts" in r}
        sources_meta.append(provenance.source(
            "openFDA MAUDE device adverse events (by event type)",
            openfda.MAUDE, fetched_at=_now(),
            records_scanned=sum(r.get("total", 0) for r in maude)))

    if not per_source_series:
        jsonio.write_site_json(
            "p3_reactive_index.json",
            provenance.envelope(
                pipeline="p3_reactive", output="reactive_index", status="unavailable",
                status_reason="all sources failed: " + "; ".join(caveats_extra),
                sources=[], coverage=None,
                caveats=["No data fetched; nothing shown rather than fabricated data."],
                methodology_id="p3_reactive_index"),
            None)
        return

    # --- normalize and blend ---
    indexed = {src: _index_to_base(series, labels)
               for src, series in per_source_series.items()}
    blended = []
    for q in labels:
        vals = [idx[q] for idx in indexed.values() if q in idx]
        blended.append({"quarter": q,
                        "index": round(sum(vals) / len(vals), 1) if vals else None,
                        "sources_available": len(vals)})

    status = "ok" if len(per_source_series) >= 3 else "partial"
    caveats = [
        "Counts what is REPORTED to regulators (recalls, complaints, adverse events), which is a proxy for physical product failures - not a measurement of Exponent's actual engagements.",
        f"Each source is indexed to its own {BASE_START}-{BASE_END} average (=100) and the blended line is the simple mean of available sources, so no single high-volume source dominates.",
        "Category tagging uses keyword matching on official descriptions (rules shown in the methodology section); keyword matching is imperfect.",
        "MAUDE adverse-event volumes grew structurally over time due to reporting-rule changes, not only because failures increased.",
        "The 0-3 month (forensic work) and 12-24 month (litigation work) lags shown against Exponent revenue are a HYPOTHESIS overlay, not a fitted statistical model.",
        "The most recent quarter is incomplete (reports keep arriving after quarter-end).",
    ] + caveats_extra

    jsonio.write_site_json(
        "p3_reactive_index.json",
        provenance.envelope(
            pipeline="p3_reactive", output="reactive_index", status=status,
            status_reason=None if status == "ok" else "; ".join(caveats_extra) or "fewer than 3 sources",
            sources=sources_meta,
            coverage={"start": labels[0], "end": labels[-1]},
            caveats=caveats, methodology_id="p3_reactive_index"),
        {"blended_index": blended,
         "per_source": {src: [{"quarter": q, **series[q]} for q in labels if q in series]
                        for src, series in per_source_series.items()},
         "per_source_indexed": indexed,
         "severity_weights": SEVERITY_WEIGHTS,
         "category_keywords": {k: v for k, v in CATEGORY_KEYWORDS.items()},
         "base_period": f"{BASE_START}-{BASE_END}"},
    )
    log.info("P3 complete: %d sources, %d quarters", len(per_source_series), len(labels))
