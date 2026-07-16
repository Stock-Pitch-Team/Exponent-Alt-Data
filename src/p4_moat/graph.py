"""Transform OpenAlex works into publication series + corporate collaboration graph."""
from collections import defaultdict

from config import entities

EXPONENT_ID_URL = f"https://openalex.org/{entities.OPENALEX_INSTITUTION_ID}"


def publications_by_year(works: list[dict]) -> list[dict]:
    per_year = defaultdict(lambda: {"works": 0, "citations": 0})
    for w in works:
        y = w.get("publication_year")
        if not y:
            continue
        per_year[y]["works"] += 1
        per_year[y]["citations"] += w.get("cited_by_count") or 0
    return [{"year": y, **per_year[y]} for y in sorted(per_year)]


def citations_received_by_year(works: list[dict], vintage_years=(5, 10)) -> dict:
    """Citations RECEIVED per calendar year, across the whole corpus.

    publications_by_year() credits citations to the year a paper was PUBLISHED,
    which makes recent years look like a collapse purely because new papers have
    not had time to be cited - a recency artefact, not a decline in relevance.
    This instead asks: in calendar year Y, how often was Exponent's science cited
    by anyone? That is the live relevance measure.

    Also splits out citations earned by RECENT work (papers published within the
    last N years as of each citing year), which separates "the back catalogue is
    coasting" from "current output is landing".
    """
    total = defaultdict(int)
    recent = {n: defaultdict(int) for n in vintage_years}
    for w in works:
        pub = w.get("publication_year")
        for row in w.get("counts_by_year") or []:
            year, cites = row.get("year"), row.get("cited_by_count") or 0
            if not year:
                continue
            total[year] += cites
            if pub is None:
                continue
            for n in vintage_years:
                if 0 <= year - pub < n:
                    recent[n][year] += cites
    years = sorted(total)
    return {
        "series": [{"year": y, "citations_received": total[y],
                    **{f"from_last_{n}y_work": recent[n].get(y, 0) for n in vintage_years}}
                   for y in years],
        "vintage_windows": list(vintage_years),
    }


def corporate_partners(works: list[dict]):
    """Company co-author institutions per work.

    Returns (per_company, per_work_companies) where per_company maps
    institution id -> {name, works, years, topics}.
    """
    per_company = {}
    per_work = []
    for w in works:
        seen_ids = set()
        for auth in w.get("authorships") or []:
            for inst in auth.get("institutions") or []:
                iid = inst.get("id")
                if not iid or iid == EXPONENT_ID_URL:
                    continue
                if inst.get("type") != "company":
                    continue
                if iid in seen_ids:
                    continue
                seen_ids.add(iid)
                entry = per_company.setdefault(iid, {
                    "id": iid,
                    "name": inst.get("display_name") or "?",
                    "works": 0,
                    "years": [],
                    "topics": defaultdict(int),
                })
                entry["works"] += 1
                y = w.get("publication_year")
                if y:
                    entry["years"].append(y)
                topic = (w.get("primary_topic") or {}).get("display_name")
                if topic:
                    entry["topics"][topic] += 1
        if seen_ids:
            per_work.append({
                "year": w.get("publication_year"),
                "companies": sorted(seen_ids),
                "title": w.get("display_name"),
                "cited_by": w.get("cited_by_count") or 0,
            })
    for entry in per_company.values():
        topics = sorted(entry["topics"].items(), key=lambda kv: -kv[1])[:3]
        entry["top_topics"] = [t for t, _ in topics]
        entry["first_year"] = min(entry["years"]) if entry["years"] else None
        entry["last_year"] = max(entry["years"]) if entry["years"] else None
        del entry["topics"]
        del entry["years"]
    return per_company, per_work


def rolling_unique_partners(per_work: list[dict], window: int = 3) -> list[dict]:
    """Unique corporate partners in each trailing `window`-year period."""
    years = sorted({pw["year"] for pw in per_work if pw["year"]})
    if not years:
        return []
    out = []
    for year in range(min(years), max(years) + 1):
        lo = year - window + 1
        companies = set()
        n_works = 0
        for pw in per_work:
            if pw["year"] and lo <= pw["year"] <= year:
                companies.update(pw["companies"])
                n_works += 1
        out.append({"year": year, "unique_partners": len(companies),
                    "coauthored_works": n_works})
    return out
