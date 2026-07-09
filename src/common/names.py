"""Person/company name normalization and fuzzy matching helpers."""
import difflib
import re

_COMPANY_SUFFIXES = re.compile(
    r"\b(incorporated|corporation|company|holdings?|group|international|"
    r"inc|corp|co|llc|llp|lp|ltd|plc|sa|ag|nv|gmbh)\b\.?", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")


def normalize_company(name: str) -> str:
    s = name.lower()
    s = _NON_ALNUM.sub(" ", s)
    s = _COMPANY_SUFFIXES.sub(" ", s)
    return _WS.sub(" ", s).strip()


def normalize_person(name: str) -> str:
    s = name.lower()
    s = re.sub(r"\b(dr|mr|mrs|ms|prof|phd|ph d|pe|md|jr|sr|ii|iii)\b\.?", " ", s)
    s = _NON_ALNUM.sub(" ", s)
    return _WS.sub(" ", s).strip()


def slug_to_name(slug: str) -> str:
    """'rob-sunley' -> 'Rob Sunley'."""
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def best_match(query: str, candidates: list[str], cutoff: float = 0.92):
    """Return (candidate, score) of the best difflib match above cutoff, else None."""
    best, best_score = None, 0.0
    for cand in candidates:
        score = difflib.SequenceMatcher(None, query, cand).ratio()
        if score > best_score:
            best, best_score = cand, score
    if best is not None and best_score >= cutoff:
        return best, best_score
    return None
