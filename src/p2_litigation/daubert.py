"""Daubert / Rule 702 outcome classification from opinion text.

Regex classification over legal prose is imperfect by nature; anything the
patterns cannot call confidently lands in 'unclassified' and is shown as such.
Every classified case links to the full opinion so a human can verify.
"""
import logging
import re

log = logging.getLogger(__name__)

# window around challenge language, in characters
_WINDOW = 2500

# case-sensitive with word boundary: must NOT match Spanish 'exponente' or math 'exponent'
_EXPONENT_RE = re.compile(r"\bExponent\b|Failure Analysis Associates")
_CHALLENGE_RE = re.compile(r"Daubert|Rule 702|motion to exclude|motion in limine",
                           re.IGNORECASE)

_PATTERNS = [
    # (label, regex) — first match wins, checked in order
    ("granted_in_part", re.compile(
        r"(?:grant(?:ed|s)?\s+in\s+part\s+and\s+den(?:ied|y|ies)?\s+in\s+part|"
        r"den(?:ied|y|ies)?\s+in\s+part\s+and\s+grant(?:ed|s)?\s+in\s+part)",
        re.IGNORECASE)),
    ("excluded", re.compile(
        r"(?:motion[s]?\s+to\s+exclude[^.]{0,120}?\bgranted\b|"
        r"\bgrant(?:ed|s)?\b[^.]{0,120}?motion[s]?\s+to\s+exclude|"
        r"\bexclude[sd]?\b[^.]{0,80}?\btestimony\b[^.]{0,80}?\bgranted\b|"
        r"testimony\s+(?:of\s+[^.]{0,60}\s+)?is\s+(?:hereby\s+)?excluded|"
        r"may\s+not\s+testify|is\s+not\s+permitted\s+to\s+testify|"
        r"\bstrik(?:e|ing)\b[^.]{0,60}\bexpert\b[^.]{0,60}\bgranted\b)",
        re.IGNORECASE)),
    ("admitted", re.compile(
        r"(?:motion[s]?\s+to\s+exclude[^.]{0,120}?\bdenied\b|"
        r"\bden(?:ied|y|ies)\b[^.]{0,120}?motion[s]?\s+to\s+exclude|"
        r"\bden(?:ied|y|ies)\b[^.]{0,80}?\bDaubert\b|"
        r"Daubert\s+motion[^.]{0,80}?\bdenied\b|"
        r"testimony\s+is\s+(?:therefore\s+)?admissible|"
        r"may\s+testify|is\s+permitted\s+to\s+testify|"
        r"motion\s+in\s+limine[^.]{0,100}?\bdenied\b)",
        re.IGNORECASE)),
]


def classify(text: str, require_exponent: bool) -> dict:
    """Classify a Daubert-type opinion. Returns {outcome, evidence_quote}."""
    if not text:
        return {"outcome": "unclassified", "reason": "no text available"}
    windows = []
    for m in _CHALLENGE_RE.finditer(text):
        lo = max(0, m.start() - _WINDOW // 2)
        window = text[lo:m.start() + _WINDOW // 2]
        if require_exponent and not _EXPONENT_RE.search(window):
            continue
        windows.append(window)
    if not windows:
        return {"outcome": "unclassified",
                "reason": "no challenge language near an Exponent mention"
                if require_exponent else "no challenge language found"}
    votes = {}
    quotes = {}
    for w in windows:
        for label, pat in _PATTERNS:
            m = pat.search(w)
            if m:
                votes[label] = votes.get(label, 0) + 1
                quotes.setdefault(label, re.sub(r"\s+", " ", m.group(0))[:200])
                break
    if not votes:
        return {"outcome": "unclassified", "reason": "no outcome language matched"}
    outcome = max(votes, key=votes.get)
    if len(votes) > 1 and "granted_in_part" not in votes:
        # conflicting signals across windows -> partial/mixed
        outcome = "mixed_signals"
    return {"outcome": outcome, "evidence_quote": quotes.get(outcome)
            or next(iter(quotes.values())), "windows": len(windows)}
