"""R&D expense per revealed client (companyfacts) + market-wide baseline (frames)."""
import logging

from src.common import edgar, http

log = logging.getLogger(__name__)

RND_TAG = "ResearchAndDevelopmentExpense"


def client_series(matched: list[dict], start_year: int = 2012) -> list[dict]:
    out = []
    for client in matched:
        try:
            facts = edgar.companyfacts(int(client["cik"]))
        except http.SourceUnavailable as exc:
            out.append({**client, "rnd_annual": None,
                        "rnd_note": f"EDGAR fetch failed: {exc.reason}"})
            continue
        series = [p for p in edgar.annual_series(facts, RND_TAG)
                  if int(p["period"]) >= start_year]
        out.append({**client,
                    "rnd_annual": [{"year": int(p["period"]), "value": p["value"]}
                                   for p in series] or None,
                    "rnd_note": None if series else
                    "company does not report the ResearchAndDevelopmentExpense tag"})
    return out


def market_baseline(start_year: int, end_year: int) -> list[dict]:
    """Sum of reported R&D across ALL SEC filers per calendar year (XBRL frames)."""
    out = []
    for year in range(start_year, end_year + 1):
        try:
            doc = edgar.frames(RND_TAG, f"CY{year}")
        except http.SourceUnavailable as exc:
            log.warning("frames CY%d failed: %s", year, exc)
            out.append({"year": year, "total": None, "filers": None})
            continue
        rows = doc.get("data", [])
        out.append({"year": year,
                    "total": sum(r.get("val") or 0 for r in rows),
                    "filers": len(rows)})
    return out
