"""Derive the 'revealed client' list from P4 co-authors and P2 case parties.

Exponent discloses no client list; this is a documented lower-bound sample:
- research_partner  (high confidence): corporation co-authored publications with Exponent
- associated_party  (lower confidence): corporation was a party in a case where
  Exponent appears near expert-witness language (side usually unknown)
"""
import json
import logging
import re

from config import settings

log = logging.getLogger(__name__)

_COUNTRY_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
_COMPANYISH = re.compile(
    r"\b(inc|corp|corporation|co|company|llc|llp|ltd|plc|group|holdings|"
    r"industries|motors|labs|laboratories|pharmaceuticals|technologies)\b\.?",
    re.IGNORECASE)
_NOT_COMPANY = re.compile(
    r"\b(united states|state of|commonwealth|people of|city of|county of|"
    r"department|commission|administrator|secretary|attorney general|estate of|"
    r"in re|ex parte)\b", re.IGNORECASE)


def research_partners(min_works: int = 2) -> list[dict]:
    path = settings.INTERIM_DIR / "p4_partners.json"
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [{"name": _COUNTRY_PAREN.sub("", r["name"]),
             "relationship": "research_partner",
             "evidence_count": r["works"],
             "evidence": f"{r['works']} co-authored publications "
                         f"({r['first_year']}-{r['last_year']})"}
            for r in rows if r["works"] >= min_works]


def case_parties() -> list[dict]:
    path = settings.INTERIM_DIR / "p2_parties.json"
    if not path.exists():
        log.warning("p2_parties.json missing - run P2 first; proceeding without")
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    seen: dict = {}
    for r in rows:
        for side in ("plaintiff", "defendant"):
            name = (r.get(side) or "").strip().rstrip(",.")
            if not name or len(name) > 80:
                continue
            if _NOT_COMPANY.search(name) or not _COMPANYISH.search(name):
                continue
            entry = seen.setdefault(name, {"name": name,
                                           "relationship": "associated_party",
                                           "evidence_count": 0, "cases": []})
            entry["evidence_count"] += 1
            if len(entry["cases"]) < 3:
                entry["cases"].append(r.get("case_name"))
    out = list(seen.values())
    for e in out:
        e["evidence"] = f"party in {e['evidence_count']} matched case(s), e.g. " + \
                        "; ".join(filter(None, e["cases"]))
        del e["cases"]
    return out


def combined(min_party_cases: int = 1) -> list[dict]:
    partners = research_partners()
    parties = [p for p in case_parties() if p["evidence_count"] >= min_party_cases]
    by_name = {}
    for row in partners + parties:
        key = row["name"].lower()
        if key in by_name:
            # research_partner wins as the stronger relationship label
            by_name[key]["evidence_count"] += row["evidence_count"]
            if by_name[key]["relationship"] != "research_partner":
                by_name[key]["relationship"] = row["relationship"]
        else:
            by_name[key] = dict(row)
    return sorted(by_name.values(), key=lambda r: -r["evidence_count"])
