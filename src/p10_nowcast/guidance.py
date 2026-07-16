"""Management's own forward guidance, parsed verbatim from EXPO's 8-K releases.

The nowcast (build.py) is deliberately blind to this: it fuses three quantitative
signals and nothing else. This module supplies the SECOND OPINION shown next to
the call - what the people running the firm told the market to expect for the
same quarter we're predicting.

Nothing here is classified, scored or modelled. We locate the "Business Outlook"
section of the most recent earnings release and lift the sentences whole, with
the accession number, so a reader checks the primary source in one click. The
guidance is a cross-check on the model, never an input to it.
"""
import logging
import re
from datetime import datetime, timezone

from src.common import http, jsonio, provenance
from src.p7_utilization import edgar_8k

log = logging.getLogger(__name__)

EXPO_CIK = 851520
MAX_FILINGS = 8   # ~2 years of 8-Ks; earnings releases are a subset

_OUTLOOK = re.compile(r"Business\s+Outlook", re.IGNORECASE)
# "For the second quarter of fiscal 2026 ... Exponent anticipates: <items>"
_PERIOD_BLOCK = re.compile(
    r"For the (?P<period>(?:first|second|third|fourth) quarter of fiscal \d{4}|"
    r"full fiscal year \d{4})[^.]{0,120}?"
    r"Exponent (?:anticipates|expects|is maintaining its guidance and anticipates|"
    r"is (?:raising|lowering) its guidance and anticipates)\s*:?\s*"
    r"(?P<items>.{0,400}?)(?=For the |“|\"|$)",
    re.IGNORECASE | re.DOTALL)
_QUARTER_WORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}
# an executive quote that states an operating metric we independently track
_METRIC_QUOTE = re.compile(r"[“\"][^”\"]{0,600}?"
                           r"(utilization|headcount|rate realization)"
                           r"[^”\"]{0,600}?[”\"]", re.IGNORECASE)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(s):
    s = re.sub(r"\s+", " ", s).strip()
    # press releases carry a footnote marker on the non-GAAP metric ("EBITDA 1 to be
    # 27.0%..."); the stray digit reads as a typo once lifted out of the exhibit
    return re.sub(r"\b(EBITDA|EPS)\s+\d\b", r"\1", s)


def _accession_url(accession):
    plain = accession.replace("-", "")
    return (f"https://www.sec.gov/Archives/edgar/data/{EXPO_CIK}/{plain}/"
            f"{accession}-index.htm")


def _period_to_quarter(period):
    """'second quarter of fiscal 2026' -> '2026-Q2'; full-year -> 'FY2026'."""
    m = re.match(r"(first|second|third|fourth) quarter of fiscal (\d{4})",
                 period, re.IGNORECASE)
    if m:
        return f"{m.group(2)}-Q{_QUARTER_WORD[m.group(1).lower()]}"
    m = re.match(r"full fiscal year (\d{4})", period, re.IGNORECASE)
    return f"FY{m.group(1)}" if m else None


def _parse_outlook(text, filed, accession):
    i = text.find("Business Outlook")
    if i < 0:
        m = _OUTLOOK.search(text)
        if not m:
            return None
        i = m.start()
    section = text[i:i + 3000]
    items = []
    for m in _PERIOD_BLOCK.finditer(section):
        raw = _clean(m.group("items"))
        # split the "Revenues ...; and, EBITDA ..." list into separate statements
        parts = [p.strip(" ;.") for p in re.split(r";\s*and,?\s*|;\s*", raw) if p.strip(" ;.")]
        items.append({
            "period": _clean(m.group("period")),
            "quarter": _period_to_quarter(_clean(m.group("period"))),
            "statements": [p for p in parts if len(p) > 8][:4],
            "verbatim": raw[:400],
        })
    quote = None
    qm = _METRIC_QUOTE.search(section)
    if qm:
        quote = _clean(qm.group(0))[:400]
    if not items and not quote:
        return None
    return {"filed": filed, "accession": accession,
            "url": _accession_url(accession), "guidance": items, "quote": quote}


def latest_guidance(use_cache=True):
    """Most recent 8-K carrying a Business Outlook section, or None."""
    filings = edgar_8k.list_filings(EXPO_CIK, ("8-K",), use_cache=use_cache)[:MAX_FILINGS]
    for filing in filings:
        try:
            texts = edgar_8k.exhibit_texts(EXPO_CIK, filing["accession"],
                                           use_cache=use_cache)
        except http.SourceUnavailable as exc:
            log.warning("8-K %s unavailable: %s", filing["accession"], exc.reason)
            continue
        for text in texts:
            if not _OUTLOOK.search(text):
                continue
            parsed = _parse_outlook(text, filing["filed"], filing["accession"])
            if parsed:
                return parsed
    return None


def run(step=None, use_cache=True):
    doc = latest_guidance(use_cache=use_cache)
    if not doc:
        jsonio.write_site_json(
            "p10_mgmt_guidance.json",
            provenance.envelope(
                pipeline="p10_nowcast", output="mgmt_guidance", status="unavailable",
                status_reason="no Business Outlook section found in recent EXPO 8-K exhibits",
                sources=[], coverage=None,
                caveats=["Nothing shown rather than a guess at what management said."],
                methodology_id="p10_mgmt_guidance"),
            None)
        log.warning("P10 guidance: no outlook section found")
        return

    jsonio.write_site_json(
        "p10_mgmt_guidance.json",
        provenance.envelope(
            pipeline="p10_nowcast", output="mgmt_guidance", status="ok",
            status_reason=None,
            sources=[provenance.source(
                f"Exponent 8-K earnings release, filed {doc['filed']} "
                f"(accession {doc['accession']})",
                doc["url"], fetched_at=_now(), records_matched=len(doc["guidance"]))],
            coverage={"start": doc["filed"], "end": doc["filed"]},
            caveats=[
                "VERBATIM from Exponent's own earnings release - lifted whole, not summarised, scored or interpreted. Click through and read the original.",
                "This is NOT an input to the nowcast. The model uses three quantitative signals and is deliberately blind to management commentary; guidance is shown beside it as an independent second opinion.",
                "Management guides REVENUE growth and EBITDA margin - not utilization directly. Since revenue is roughly headcount x utilization x rate, their revenue guide implies a utilization path only in combination with the headcount and rate data on this page.",
                "Guidance is an interested party's forecast: companies guide conservatively and revise. It is evidence, not truth.",
            ],
            methodology_id="p10_mgmt_guidance"),
        doc)
    log.info("P10 guidance: %d periods from 8-K filed %s (quote: %s)",
             len(doc["guidance"]), doc["filed"], bool(doc["quote"]))
