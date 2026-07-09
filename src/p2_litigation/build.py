"""P2 build: litigation-demand time series, Daubert win rate, evidence table."""
import json
import logging
import re
from collections import defaultdict
from datetime import date, datetime, timezone

from config import settings
from src.common import http, jsonio, provenance, quarters
from src.p2_litigation import daubert, fetch

log = logging.getLogger(__name__)

OPINIONS_START = 1990
RECAP_START = 2005
RECAP_PAGE_START = 2018         # page full RECAP results only for recent years (recency
                                # focus); older years use one count request apiece
DAUBERT_FETCH_CAP = 40          # Exponent-linked opinions to pull full text for
BASELINE_FETCH_CAP = 40         # non-Exponent Daubert opinions for the baseline

_V_RE = re.compile(r"\s+v\.?\s+", re.IGNORECASE)

# CourtListener's stemmer matches Spanish 'exponente' (a common legal word in
# Puerto Rico opinions) against 'Exponent'. For Spanish-language PR state courts,
# keep a record only if a snippet contains the firm's exact English name.
_PR_SPANISH_IDS = ("prsupreme", "prapp")
_STRICT_FIRM_RE = re.compile(r"\b(Exponent|Failure Analysis Associates)\b")


def _spanish_false_positive(rec: dict) -> bool:
    court_id = (rec.get("court_id") or "").lower()
    court = rec.get("court") or ""
    is_spanish_court = (court_id in _PR_SPANISH_IDS or "Tribunal" in court
                        or court == "Supreme Court of Puerto Rico")
    if not is_spanish_court:
        return False
    return not _STRICT_FIRM_RE.search(" ".join(rec.get("snippets") or []))


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(step=None, use_cache=True):
    end_year = date.today().year
    interim = settings.INTERIM_DIR
    partial_reason = None
    results_o, results_r, legacy = [], [], []
    recap_counts = {}
    baselines = {"o": {}, "r": {}}
    try:
        # --- loose query result records, year by year ---
        dropped_fp = 0
        for year in range(OPINIONS_START, end_year + 1):
            for rec in fetch.search_year(fetch.Q_LOOSE, "o", year):
                if _spanish_false_positive(rec):
                    dropped_fp += 1
                else:
                    results_o.append(rec)
        for year in range(RECAP_START, end_year + 1):
            if year < RECAP_PAGE_START:
                recap_counts[year] = fetch.count(fetch.Q_LOOSE, "r", year)
            else:
                for rec in fetch.search_year(fetch.Q_LOOSE, "r", year):
                    if _spanish_false_positive(rec):
                        dropped_fp += 1
                    else:
                        results_r.append(rec)
        log.info("dropped %d Spanish-court false positives", dropped_fp)
        # legacy company name (pre-1998), small volume: page all-time
        legacy = _search_all(fetch.Q_LEGACY, "o")
        # --- baseline denominators (all filings, no query) ---
        for year in range(OPINIONS_START, end_year + 1):
            baselines["o"][year] = fetch.count(None, "o", year)
        for year in range(RECAP_START, end_year + 1):
            baselines["r"][year] = fetch.count(None, "r", year)
    except (fetch.QuotaExhausted, http.SourceUnavailable) as exc:
        partial_reason = f"stopped early: {exc}; re-run to resume from cache"
        log.warning(partial_reason)

    _write_timeseries(results_o, results_r, legacy, baselines, recap_counts,
                      end_year, partial_reason)
    _write_evidence_and_parties(results_o, results_r, interim)

    # --- Daubert win rate ---
    try:
        _build_daubert()
    except (fetch.QuotaExhausted, http.SourceUnavailable) as exc:
        log.warning("daubert stage stopped: %s", exc)
        jsonio.write_site_json(
            "p2_daubert.json",
            provenance.envelope(
                pipeline="p2_litigation", output="daubert", status="unavailable",
                status_reason=f"fetch stopped early: {exc}; re-run to resume",
                sources=[], coverage=None,
                caveats=["No opinions fetched yet; nothing shown rather than fabricated data."],
                methodology_id="p2_daubert"),
            None)


def _search_all(q: str, type_: str, max_pages: int = 10) -> list[dict]:
    out = []
    doc = fetch.cl_get(fetch.SEARCH_URL, {"q": q, "type": type_})
    pages = 1
    while True:
        for r in doc.get("results", []):
            out.append(fetch._slim(r, type_))
        nxt = doc.get("next")
        if not nxt or pages >= max_pages:
            return out
        doc = fetch.cl_get(nxt)
        pages += 1


def _write_timeseries(results_o, results_r, legacy, baselines, recap_counts,
                      end_year, partial_reason):
    def yearly(records):
        c = defaultdict(int)
        for r in records:
            d = r.get("date_filed") or ""
            if len(d) >= 4:
                c[int(d[:4])] += 1
        return c
    o_yearly, r_yearly, legacy_yearly = yearly(results_o), yearly(results_r), yearly(legacy)
    series = []
    for year in range(OPINIONS_START, end_year + 1):
        base_o, base_r = baselines["o"].get(year), baselines["r"].get(year)
        if year < RECAP_START:
            recap_n = None
        elif year in recap_counts:      # pre-2018: count query only
            recap_n = recap_counts[year]
        else:                           # 2018+: counted from paged records
            recap_n = r_yearly.get(year, 0)
        row = {"year": year,
               "opinions_mentions": o_yearly.get(year, 0),
               "recap_mentions": recap_n,
               "legacy_name_mentions": legacy_yearly.get(year, 0),
               "opinions_total": base_o,
               "recap_total": base_r if year >= RECAP_START else None}
        row["opinions_per_100k"] = (round(row["opinions_mentions"] / base_o * 100000, 2)
                                    if base_o else None)
        row["recap_per_100k"] = (round(recap_n / base_r * 100000, 2)
                                 if (base_r and recap_n is not None) else None)
        series.append(row)

    status = "partial" if partial_reason else "ok"
    jsonio.write_site_json(
        "p2_litigation_timeseries.json",
        provenance.envelope(
            pipeline="p2_litigation", output="litigation_timeseries", status=status,
            status_reason=partial_reason,
            sources=[provenance.source(
                "CourtListener v4 search API (Free Law Project)",
                fetch.SEARCH_URL, fetched_at=_now(),
                records_matched=len(results_o) + len(results_r) + len(legacy),
                note=f'query: {fetch.Q_LOOSE}')],
            coverage={"start": str(OPINIONS_START), "end": str(end_year)},
            caveats=[
                "Counts court opinions / federal-case documents where 'Exponent' appears near expert-witness language - the TESTIFYING tip of the iceberg. Consulting (non-testifying) engagements and most state-court work are invisible here.",
                "The word 'Exponent' has non-firm meanings; the expert-context query removes most but not all false positives. Match snippets are kept so cases can be verified.",
                "RECAP coverage only includes federal dockets that some RECAP user purchased from PACER - coverage grows over time and skews to high-profile cases. Use the per-100k normalized line, not raw counts.",
                "CourtListener's own opinion coverage varies by court and era; normalization by total filings per year corrects for indexing growth.",
                "Spanish-language Puerto Rico state-court opinions are screened out: CourtListener's word-stemming matches the common Spanish legal word 'exponente' against 'Exponent', and these courts were added to the archive in bulk after 2023. Removed matches are counted and disclosed in the pipeline log.",
                "The court MIX of the archive also shifts over time, which can inflate the recent normalized rate; raw mention counts are shown alongside so both can be read together.",
                "'Failure Analysis Associates' is Exponent's pre-1998 name, shown separately.",
            ],
            methodology_id="p2_litigation_timeseries"),
        {"series": series},
    )
    log.info("P2 timeseries: %d opinion + %d recap + %d legacy records",
             len(results_o), len(results_r), len(legacy))


def _write_evidence_and_parties(results_o, results_r, interim):
    recent = sorted(results_o + results_r,
                    key=lambda r: r.get("date_filed") or "", reverse=True)
    evidence = [{k: r.get(k) for k in
                 ("case_name", "court", "date_filed", "docket_number", "url",
                  "type", "snippets")} for r in recent[:250]]
    jsonio.write_site_json(
        "p2_matched_cases.json",
        provenance.envelope(
            pipeline="p2_litigation", output="matched_cases",
            status="ok" if evidence else "partial",
            status_reason=None if evidence else "no matched cases fetched yet",
            sources=[provenance.source(
                "CourtListener v4 search API (Free Law Project)", fetch.SEARCH_URL,
                fetched_at=_now(), records_matched=len(recent))],
            coverage=None,
            caveats=[
                "Most recent 250 matched cases shown; every row links to the source docket/opinion on CourtListener for verification.",
                "A case mentioning Exponent near expert language does not reveal which side retained the firm unless the text says so.",
            ],
            methodology_id="p2_matched_cases"),
        {"cases": evidence, "total_matched": len(recent)},
    )
    # party extraction for P6
    parties = []
    for r in recent:
        name = r.get("case_name") or ""
        parts = _V_RE.split(name, maxsplit=1)
        if len(parts) == 2:
            parties.append({"plaintiff": parts[0].strip(), "defendant": parts[1].strip(),
                            "case_name": name, "date_filed": r.get("date_filed"),
                            "court": r.get("court"), "url": r.get("url")})
    (interim / "p2_parties.json").write_text(
        json.dumps(parties, indent=0), encoding="utf-8")
    log.info("P2 evidence: %d cases, %d party rows", len(evidence), len(parties))


def _build_daubert():
    exponent_cases = [c for c in _search_all(fetch.Q_DAUBERT, "o", max_pages=6)
                      if not _spanish_false_positive(c)]
    classified = []
    for case in exponent_cases[:DAUBERT_FETCH_CAP]:
        text = ""
        for oid in (case.get("opinion_ids") or [])[:1]:
            text = fetch.opinion_text(oid)
        result = daubert.classify(text, require_exponent=True)
        classified.append({**{k: case.get(k) for k in
                              ("case_name", "court", "date_filed", "url")},
                           **result})
    # baseline: most recent non-Exponent Daubert opinions, same classifier
    base_doc = fetch.cl_get(fetch.SEARCH_URL, {
        "q": fetch.Q_DAUBERT_BASELINE, "type": "o", "order_by": "dateFiled desc"})
    baseline_cases = []
    pages = 1
    while len(baseline_cases) < BASELINE_FETCH_CAP and base_doc:
        for r in base_doc.get("results", []):
            baseline_cases.append(fetch._slim(r, "o"))
        nxt = base_doc.get("next")
        base_doc = fetch.cl_get(nxt) if (nxt and pages < 5) else None
        pages += 1
    baseline_classified = []
    for case in baseline_cases[:BASELINE_FETCH_CAP]:
        text = ""
        for oid in (case.get("opinion_ids") or [])[:1]:
            text = fetch.opinion_text(oid)
        result = daubert.classify(text, require_exponent=False)
        baseline_classified.append(result)

    def rate(rows):
        called = [r for r in rows if r["outcome"] in
                  ("excluded", "admitted", "granted_in_part")]
        if not called:
            return None, 0
        excluded = sum(1 for r in called if r["outcome"] == "excluded")
        partial = sum(1 for r in called if r["outcome"] == "granted_in_part")
        return round((excluded + 0.5 * partial) / len(called), 3), len(called)

    expo_rate, expo_n = rate(classified)
    base_rate, base_n = rate(baseline_classified)
    jsonio.write_site_json(
        "p2_daubert.json",
        provenance.envelope(
            pipeline="p2_litigation", output="daubert", status="ok",
            sources=[provenance.source(
                "CourtListener opinions (full text fetched per case)",
                fetch.SEARCH_URL, fetched_at=_now(),
                records_scanned=len(classified) + len(baseline_classified),
                records_matched=expo_n + base_n,
                note=f"exponent query: {fetch.Q_DAUBERT}")],
            coverage=None,
            caveats=[
                f"SMALL SAMPLE: {expo_n} Exponent-linked and {base_n} baseline opinions had a classifiable outcome; read the rate as indicative, not precise.",
                "Outcomes are classified by pattern-matching legal language; 'unclassified' and 'mixed_signals' rows are shown, never guessed. Every case links to the full opinion for human verification.",
                "The baseline is the most recent non-Exponent Daubert/Rule-702 opinions run through the SAME classifier, so classifier bias applies equally to both groups.",
                "An exclusion ruling may target any expert in the case, not necessarily the Exponent-affiliated one, when multiple experts are challenged in one opinion.",
            ],
            methodology_id="p2_daubert"),
        {"exponent": {"exclusion_rate": expo_rate, "n_classified": expo_n,
                      "cases": classified},
         "baseline": {"exclusion_rate": base_rate, "n_classified": base_n,
                      "outcome_counts": _tally(baseline_classified)},
         "exponent_outcome_counts": _tally(classified)},
    )
    log.info("P2 daubert: exponent %s (n=%d) vs baseline %s (n=%d)",
             expo_rate, expo_n, base_rate, base_n)


def _tally(rows):
    t = defaultdict(int)
    for r in rows:
        t[r["outcome"]] += 1
    return dict(t)
