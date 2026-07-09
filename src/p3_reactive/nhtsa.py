"""NHTSA ODI flat-file parsing: recalls (FLAT_RCL_POST_2010) + complaints (FLAT_CMPL).

Files are tab-delimited, latin-1, one record per line, no header
(layouts: static.nhtsa.gov/odi/ffdd/rcl/RCL.txt and /cmpl/CMPL.txt).
Streamed straight out of the zip; only quarterly aggregates are kept.
"""
import io
import logging
import zipfile

from config.categories import CATEGORY_KEYWORDS, SEVERITY_WEIGHTS

log = logging.getLogger(__name__)

RECALLS_URL = "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip"
COMPLAINTS_URL = "https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip"

# 0-indexed columns per the published layouts
RCL_CAMPNO, RCL_COMPNAME, RCL_MFGNAME, RCL_RCDATE = 1, 6, 7, 15
RCL_DESC, RCL_CONSEQ = 19, 20
CMPL_FAILDATE, CMPL_FIRE, CMPL_INJURED, CMPL_DEATHS = 7, 8, 9, 10
CMPL_COMPDESC, CMPL_LDATE, CMPL_CDESCR = 11, 16, 19


def _iter_rows(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            with z.open(name) as fh:
                for line in io.TextIOWrapper(fh, encoding="latin-1", newline=""):
                    yield line.rstrip("\r\n").split("\t")


def _date_to_quarter(yyyymmdd: str):
    if len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        return None
    year, month = int(yyyymmdd[:4]), int(yyyymmdd[4:6])
    if not (1 <= month <= 12) or year < 1960:
        return None
    return f"{year}-Q{(month - 1) // 3 + 1}"


def _categories(text: str) -> list[str]:
    text = text.lower()
    return [cat for cat, kws in CATEGORY_KEYWORDS.items()
            if any(kw in text for kw in kws)]


def parse_recalls(zip_path) -> tuple[dict, int, int]:
    """Return ({(quarter, category): {'count', 'weighted'}}, scanned, matched).

    Recalls are deduplicated by campaign number (the file has one row per
    affected make/model, which would overweight recalls of popular vehicles).
    """
    agg: dict = {}
    seen_campaigns: set = set()
    scanned = matched = 0
    for row in _iter_rows(zip_path):
        scanned += 1
        if len(row) <= RCL_CONSEQ:
            continue
        campno = row[RCL_CAMPNO]
        if campno in seen_campaigns:
            continue
        seen_campaigns.add(campno)
        quarter = _date_to_quarter(row[RCL_RCDATE])
        if quarter is None:
            continue
        cats = _categories(" ".join((row[RCL_COMPNAME], row[RCL_DESC], row[RCL_CONSEQ])))
        if not cats:
            continue
        matched += 1
        w = SEVERITY_WEIGHTS["nhtsa_recall"]
        for cat in cats:
            slot = agg.setdefault((quarter, cat), {"count": 0, "weighted": 0.0})
            slot["count"] += 1
            slot["weighted"] += w
    log.info("NHTSA recalls: %d rows, %d unique matched campaigns", scanned, matched)
    return agg, scanned, matched


def parse_complaints(zip_path) -> tuple[dict, int, int]:
    agg: dict = {}
    scanned = matched = 0
    for row in _iter_rows(zip_path):
        scanned += 1
        if len(row) <= CMPL_CDESCR:
            continue
        quarter = _date_to_quarter(row[CMPL_LDATE])
        if quarter is None:
            continue
        cats = _categories(row[CMPL_COMPDESC] + " " + row[CMPL_CDESCR])
        if not cats:
            continue
        matched += 1
        severe = (row[CMPL_FIRE] == "Y"
                  or _to_int(row[CMPL_INJURED]) > 0
                  or _to_int(row[CMPL_DEATHS]) > 0)
        w = SEVERITY_WEIGHTS["nhtsa_complaint_injury" if severe else "nhtsa_complaint"]
        for cat in cats:
            slot = agg.setdefault((quarter, cat), {"count": 0, "weighted": 0.0})
            slot["count"] += 1
            slot["weighted"] += w
        if scanned % 500000 == 0:
            log.info("NHTSA complaints: %d rows scanned, %d matched", scanned, matched)
    log.info("NHTSA complaints: %d rows, %d matched", scanned, matched)
    return agg, scanned, matched


def _to_int(s: str) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0
