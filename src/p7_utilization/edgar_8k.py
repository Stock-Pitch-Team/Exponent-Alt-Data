"""Fetch EXPO 8-K earnings-release exhibits from SEC EDGAR and parse the
utilization percentage and technical FTE count Exponent states each quarter.

These are the two variables the investment thesis actually turns on, straight
from the company's own filed press releases (EX-99 exhibits).
"""
import json
import logging
import re

from bs4 import BeautifulSoup

from src.common import edgar, http

log = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}"

# wording varies by era: "Utilization ... was 75%, compared to 73%",
# "76% utilization", "utilization improved to 74%"
_UTIL_COMPARE_RE = re.compile(
    r"utilization[^.%]{0,120}?(\d{2}(?:\.\d)?)\s*%[^.%]{0,80}?"
    r"(?:compared\s+(?:to|with)|versus|vs\.?)[^.%]{0,60}?(\d{2}(?:\.\d)?)\s*%",
    re.IGNORECASE | re.DOTALL)
_UTIL_PATTERNS = [
    re.compile(r"(\d{2}(?:\.\d)?)\s*%\s+utilization", re.IGNORECASE),
    re.compile(r"utilization\s+(?:rate\s+)?(?:was|of|at|improved\s+to|increased\s+to|"
               r"decreased\s+to|reached)\s+(?:approximately\s+)?(\d{2}(?:\.\d)?)\s*%",
               re.IGNORECASE),
    re.compile(r"utilization[^.%]{0,80}?(\d{2}(?:\.\d)?)\s*%", re.IGNORECASE | re.DOTALL),
]
# "5% year-over-year headcount growth" / "headcount ... was up approximately 4%"
_HEADCOUNT_PATTERNS = [
    re.compile(r"(\d{1,2}(?:\.\d)?)\s*%\s+year[-\s]over[-\s]year\s+headcount\s+growth",
               re.IGNORECASE),
    re.compile(r"headcount[^.]{0,120}?(?:up|increased|grew|growth\s+of)\s+"
               r"(?:approximately\s+|about\s+|by\s+)?(\d{1,2}(?:\.\d)?)\s*%",
               re.IGNORECASE | re.DOTALL),
    re.compile(r"(?:grew|increased|expanded)\s+(?:our\s+)?headcount\s+(?:by\s+)?"
               r"(?:approximately\s+)?(\d{1,2}(?:\.\d)?)\s*%", re.IGNORECASE),
]
# FTE appears as a metrics-table row ("Technical full-time equivalents 1,013 966")
# or a short verb phrase. Firmwide FTE is 300-1,600 over EXPO's history; segment
# figures are smaller, years are larger - callers take the max in-band candidate.
_FTE_PATTERNS = [
    re.compile(r"technical\s+full[-\s]?time\s+equivalents?(?:\s+employees)?"
               r"(?:\s*\(FTEs?\))?[\s:]{0,6}([\d,]{3,5})(?!\s*%|\d)", re.IGNORECASE),
    # "... increased 5% to 1,013 during ..." - gap may contain digits/percent
    re.compile(r"technical\s+full[-\s]?time\s+equivalents?(?:\s+employees)?"
               r"(?:\s*\(FTEs?\))?.{0,60}?(?:were|was|of|totaled|at|to)\s+"
               r"([\d,]{3,5})(?!\s*%|\d)", re.IGNORECASE | re.DOTALL),
]
# "... to 1,013 during the first quarter of 2026 as compared to 966 ..."
_FTE_COMPARE_RE = re.compile(
    r"technical\s+full[-\s]?time\s+equivalents?(?:\s+employees)?.{0,60}?"
    r"to\s+([\d,]{3,5})\s+(?:during|for|in).{0,80}?compared\s+(?:to|with)\s+"
    r"([\d,]{3,5})(?!\s*%|\d)", re.IGNORECASE | re.DOTALL)
_FTE_BAND = (300, 1600)


def list_filings(cik: int, forms: tuple, use_cache=True) -> list[dict]:
    """All filings of the given forms (accession, dates, primary doc), incl. archives."""
    raw = http.cached_get(SUBMISSIONS_URL.format(cik=cik), use_cache=use_cache)
    doc = json.loads(raw)
    batches = [doc["filings"]["recent"]]
    for extra in doc["filings"].get("files", []):
        raw2 = http.cached_get("https://data.sec.gov/submissions/" + extra["name"],
                               use_cache=use_cache)
        batches.append(json.loads(raw2))
    out = []
    for b in batches:
        n = len(b["form"])
        for i, form in enumerate(b["form"]):
            if form not in forms:
                continue
            out.append({
                "form": form,
                "accession": b["accessionNumber"][i],
                "filed": b["filingDate"][i],
                "report_date": (b.get("reportDate") or [None] * n)[i],
                "primary": (b.get("primaryDocument") or [None] * n)[i],
            })
    log.info("found %d filings of %s", len(out), forms)
    return out


def list_8k_filings(cik: int, use_cache=True) -> list[dict]:
    return list_filings(cik, ("8-K",), use_cache=use_cache)


def primary_doc_text(cik: int, filing: dict, use_cache=True) -> str:
    """Plain text of a filing's primary document (10-Q/10-K MD&A lives here)."""
    if not filing.get("primary"):
        return ""
    acc_nodash = filing["accession"].replace("-", "")
    url = f"{ARCHIVES_BASE.format(cik=cik, acc_nodash=acc_nodash)}/{filing['primary']}"
    try:
        raw = http.cached_get(url, use_cache=use_cache)
    except http.SourceUnavailable:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" "))


def exhibit_texts(cik: int, accession: str, use_cache=True) -> list[str]:
    """Plain text of the press-release-like documents in one 8-K."""
    acc_nodash = accession.replace("-", "")
    base = ARCHIVES_BASE.format(cik=cik, acc_nodash=acc_nodash)
    raw = http.cached_get(f"{base}/index.json", use_cache=use_cache)
    items = json.loads(raw).get("directory", {}).get("item", [])
    names = [it["name"] for it in items
             if re.search(r"(ex[-_]?99|press|earn|exh)", it["name"], re.IGNORECASE)
             and it["name"].lower().endswith((".htm", ".html", ".txt"))]
    if not names:  # fall back to every small htm in the filing
        names = [it["name"] for it in items
                 if it["name"].lower().endswith((".htm", ".html"))][:4]
    texts = []
    for name in names:
        try:
            raw_doc = http.cached_get(f"{base}/{name}", use_cache=use_cache)
        except http.SourceUnavailable:
            continue
        soup = BeautifulSoup(raw_doc, "html.parser")
        texts.append(re.sub(r"\s+", " ", soup.get_text(" ")))
    return texts


def parse_metrics(text: str, allow_fte: bool = True) -> dict:
    """Extract utilization % (current + year-ago), headcount growth %, FTE count."""
    out = {}
    m = _UTIL_COMPARE_RE.search(text)
    if m:
        out["utilization"] = float(m.group(1))
        out["utilization_prior_year"] = float(m.group(2))
    else:
        for pat in _UTIL_PATTERNS:
            m = pat.search(text)
            if m and 40 <= float(m.group(1)) <= 95:  # sanity band for a utilization %
                out["utilization"] = float(m.group(1))
                break
    for pat in _HEADCOUNT_PATTERNS:
        h = pat.search(text)
        if h and 0 < float(h.group(1)) <= 30:
            out["headcount_growth_pct"] = float(h.group(1))
            break
    if allow_fte:
        cm = _FTE_COMPARE_RE.search(text)
        if cm:
            cur, prior = (int(cm.group(i).replace(",", "")) for i in (1, 2))
            if all(_FTE_BAND[0] <= v <= _FTE_BAND[1] for v in (cur, prior)):
                out["fte"] = cur
                out["fte_prior_year"] = prior
        if "fte" not in out:
            candidates = []
            for pat in _FTE_PATTERNS:
                for m in pat.finditer(text):
                    v = int(m.group(1).replace(",", ""))
                    if _FTE_BAND[0] <= v <= _FTE_BAND[1]:
                        candidates.append(v)
            if candidates:
                # firmwide >= any segment figure mentioned in the same document
                out["fte"] = max(candidates)
    return out


def quarter_from_text_or_date(text: str, report_date: str | None, filed: str) -> str | None:
    """Prefer the quarter the release names; fall back to the report period."""
    m = re.search(r"(first|second|third|fourth)\s+quarter\s+(?:of\s+|and\s+full\s+year\s+)?"
                  r"(?:fiscal\s+)?(20\d{2})", text, re.IGNORECASE)
    if m:
        q = {"first": 1, "second": 2, "third": 3, "fourth": 4}[m.group(1).lower()]
        return f"{m.group(2)}-Q{q}"
    basis = report_date or filed
    if not basis:
        return None
    year, month = int(basis[:4]), int(basis[5:7])
    # earnings 8-Ks are filed ~1 month after quarter end; map back one quarter
    q = (month - 1) // 3 + 1
    q -= 1
    if q == 0:
        year, q = year - 1, 4
    return f"{year}-Q{q}"
