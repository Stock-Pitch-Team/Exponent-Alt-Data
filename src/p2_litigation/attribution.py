"""Daubert v2: attribute each Exponent-linked opinion to a named expert and
practice area using the roster spine (current directory + historical slugs).

Runs entirely from cached opinion texts - no new API requests. Unmatched
experts are labeled 'not identified', never guessed.
"""
import json
import logging
import re

from config import settings
from src.common import jsonio, names
from src.p2_litigation import fetch

log = logging.getLogger(__name__)

# person-name candidates near an Exponent mention
_NAME_NEAR_RE = re.compile(
    r"\b(?:Dr|Mr|Ms|Mrs|Prof)\.?\s+([A-Z][A-Za-z'\-]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z'\-]+)?)")
_OF_EXPONENT_RE = re.compile(
    r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][A-Za-z'\-]+)\s*(?:,\s*(?:Ph\.?D\.?|P\.?E\.?|M\.?D\.?))?"
    r"\s*,?\s*(?:of|from|at|an?\s+\w+\s+(?:at|with))\s+Exponent", re.DOTALL)
_EXPONENT_RE = re.compile(r"\bExponent\b|Failure Analysis Associates")
_WINDOW = 500


def _load_spine():
    """(normalized full name -> display name, surname+initial -> display, name -> practice)"""
    full, surname_init, practice = {}, {}, {}
    roster_path = settings.INTERIM_DIR / "p1_roster_names.json"
    if roster_path.exists():
        for name in json.loads(roster_path.read_text(encoding="utf-8")):
            display = re.sub(r",.*$", "", name).strip()  # strip credentials
            norm = names.normalize_person(display)
            if not norm:
                continue
            full[norm] = display
            parts = norm.split()
            if len(parts) >= 2:
                surname_init[(parts[-1], parts[0][0])] = display
    roster_file = settings.SITE_DATA_DIR / "p1_current_roster.json"
    if roster_file.exists():
        doc = json.loads(roster_file.read_text(encoding="utf-8"))
        for p in (doc.get("data") or {}).get("people", []):
            display = re.sub(r",.*$", "", p.get("name") or "").strip()
            if display and p.get("practice"):
                practice[names.normalize_person(display)] = p["practice"]
    hist_path = settings.INTERIM_DIR / "p1_historical_slugs.json"
    if hist_path.exists():
        eras = json.loads(hist_path.read_text(encoding="utf-8"))
        for era, slugs in eras.items():
            for slug in slugs:
                tokens = slug.split("-")
                if len(tokens) < 2:
                    continue
                # legacy era slugs are last-first; current era first-last
                ordered = tokens[1:] + tokens[:1] if era == "professionals" else tokens
                display = " ".join(t.capitalize() for t in ordered)
                norm = names.normalize_person(display)
                full.setdefault(norm, display + " (former-roster match)")
                parts = norm.split()
                if len(parts) >= 2:
                    surname_init.setdefault((parts[-1], parts[0][0]),
                                            display + " (former-roster match)")
    return full, surname_init, practice


_BIGRAM_RE = re.compile(r"\b([A-Z][a-z'\-]{2,})\s+(?:[A-Z]\.\s+)?([A-Z][a-z'\-]{2,})\b")


def _candidates(text: str) -> list[str]:
    out = []
    for m in _OF_EXPONENT_RE.finditer(text):
        out.append(m.group(1))
    for em in _EXPONENT_RE.finditer(text):
        window = text[max(0, em.start() - _WINDOW):em.start() + _WINDOW]
        for m in _NAME_NEAR_RE.finditer(window):
            out.append(m.group(1))
    return out


def _rosterwide_candidates(text: str, full: dict) -> list[str]:
    """Any roster full-name appearing anywhere in the opinion, accepted only if
    that surname also appears within +/-500 chars of an Exponent mention."""
    near_exponent = set()
    for em in _EXPONENT_RE.finditer(text):
        window = text[max(0, em.start() - _WINDOW):em.start() + _WINDOW]
        near_exponent.update(w.lower().strip(".,;:'") for w in window.split())
    out = []
    for m in _BIGRAM_RE.finditer(text):
        cand = f"{m.group(1)} {m.group(2)}"
        if names.normalize_person(cand) in full and m.group(2).lower() in near_exponent:
            out.append(cand)
    return out


def _match(candidate: str, full: dict, surname_init: dict):
    norm = names.normalize_person(candidate)
    if norm in full:
        return full[norm], "full-name"
    parts = norm.split()
    if len(parts) >= 2:
        key = (parts[-1], parts[0][0])
        if key in surname_init:
            return surname_init[key], "surname+initial"
        # opinions often use surname only after first mention - too ambiguous alone
    return None, None


def run(step=None, use_cache=True):
    doc = jsonio.read_site_json("p2_daubert.json")
    if not doc.get("data"):
        log.warning("p2_daubert.json has no data; run p2 first")
        return
    full, surname_init, practice_map = _load_spine()
    log.info("spine: %d full names, %d surname keys, %d practices",
             len(full), len(surname_init), len(practice_map))

    cases = doc["data"]["exponent"]["cases"]
    matched_n = 0
    for case in cases:
        # re-derive the opinion text from cache via the evidence url -> opinion ids
        # (cases carry no ids, so re-search is avoided: use stored quote windows +
        # fetch by cluster via matched-cases record when available)
        case.setdefault("expert", None)
        case.setdefault("expert_practice", None)
    # opinion ids come from the daubert search results, which are cached
    from src.p2_litigation.build import _search_all
    results = {r["url"]: r for r in _search_all(fetch.Q_DAUBERT, "o", max_pages=6)}
    for case in cases:
        rec = results.get(case.get("url"))
        if not rec:
            case["expert"] = case["expert"] or "not identified"
            continue
        text = ""
        for oid in (rec.get("opinion_ids") or [])[:1]:
            text = fetch.opinion_text(oid)
        best = None
        for cand in _candidates(text):
            hit, how = _match(cand, full, surname_init)
            if hit:
                best = (hit, how)
                if how == "full-name":
                    break
        if not best or best[1] != "full-name":
            for cand in _rosterwide_candidates(text, full):
                best = (full[names.normalize_person(cand)], "roster-name in opinion")
                break
        if best:
            display, how = best
            case["expert"] = display
            case["expert_match"] = how
            case["expert_practice"] = practice_map.get(
                names.normalize_person(re.sub(r"\s*\(former.*\)$", "", display)))
            matched_n += 1
        else:
            case["expert"] = "not identified"

    by_practice = {}
    for case in cases:
        p = case.get("expert_practice")
        if p:
            slot = by_practice.setdefault(p, {"cases": 0, "outcomes": {}})
            slot["cases"] += 1
            slot["outcomes"][case["outcome"]] = slot["outcomes"].get(case["outcome"], 0) + 1
    doc["data"]["by_practice"] = by_practice
    doc["metadata"]["caveats"] = [c for c in doc["metadata"]["caveats"]
                                  if not c.startswith("Expert attribution:")]
    doc["metadata"]["caveats"].append(
        f"Expert attribution: {matched_n} of {len(cases)} opinions matched to a named "
        "roster consultant (current or archived); the rest say 'not identified' rather than guessing. "
        "Practice areas come from the consultant's current directory profile.")
    jsonio.write_site_json("p2_daubert.json", doc["metadata"], doc["data"])
    log.info("attribution: %d/%d cases matched to roster experts, %d practices",
             matched_n, len(cases), len(by_practice))
