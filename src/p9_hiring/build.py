"""P9 build: Exponent's sponsored-hiring velocity from DOL disclosure data."""
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

from src.common import jsonio, provenance, quarters
from src.p9_hiring import dol

log = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _quarter(datestr):
    if not datestr or len(datestr) < 7:
        return None
    try:
        return quarters.to_quarter(datestr[:10])
    except ValueError:
        return None


def run(step=None, use_cache=True):
    rows = dol.all_rows()
    if not rows:
        jsonio.write_site_json(
            "p9_hiring.json",
            provenance.envelope(
                pipeline="p9_hiring", output="hiring", status="unavailable",
                status_reason="no Exponent rows found in downloaded DOL files",
                sources=[], coverage=None,
                caveats=["No data; nothing shown rather than fabricated data."],
                methodology_id="p9_hiring"),
            None)
        return

    # keep the consulting firm; drop unrelated employers containing 'exponent'
    firm_rows = [r for r in rows if re.match(
        r"^exponent(,?\s+inc\.?.*)?$", r["employer"].strip().lower())]
    by_q = defaultdict(lambda: {"lca": 0, "perm": 0, "certified": 0})
    titles = defaultdict(int)
    for r in firm_rows:
        q = _quarter(r.get("received"))
        if not q:
            continue
        slot = by_q[q]
        slot["lca" if r["program"] == "LCA" else "perm"] += 1
        if r.get("status") and "certified" in r["status"].lower():
            slot["certified"] += 1
        if r.get("title"):
            titles[r["title"].title()] += 1

    series = [{"quarter": q, **by_q[q]} for q in sorted(by_q, key=quarters.sort_key)]
    top_titles = sorted(titles.items(), key=lambda kv: -kv[1])[:20]
    sample = [{k: r.get(k) for k in ("program", "received", "status", "title",
                                     "city", "state", "wage", "wage_level")}
              for r in sorted(firm_rows, key=lambda r: r.get("received") or "",
                              reverse=True)[:60]]

    jsonio.write_site_json(
        "p9_hiring.json",
        provenance.envelope(
            pipeline="p9_hiring", output="hiring",
            status="ok" if len(series) >= 4 else "partial",
            status_reason=None if len(series) >= 4 else "few quarters covered",
            sources=[provenance.source(
                "US Dept. of Labor LCA (H-1B) + PERM disclosure files, FY2024-FY2026",
                "https://www.dol.gov/agencies/eta/foreign-labor/performance",
                fetched_at=_now(), records_scanned=len(rows),
                records_matched=len(firm_rows))],
            coverage={"start": series[0]["quarter"], "end": series[-1]["quarter"]}
            if series else None,
            caveats=[
                "Covers only roles where Exponent sponsored a foreign national (H-1B LCA) or a green card (PERM) - a SLICE of total hiring, but a high-signal one for a PhD-heavy firm and 100% public/legal.",
                "An LCA filing is hiring INTENT (and includes renewals/transfers); a PERM filing signals a long-term retention commitment to an existing scientist.",
                "Filed quarterly by DOL with a reporting lag; the newest quarter is incomplete.",
                "Job titles are as written on the filings.",
            ],
            methodology_id="p9_hiring"),
        {"series": series, "top_titles": [{"title": t, "count": c} for t, c in top_titles],
         "recent_filings": sample},
    )
    log.info("P9: %d Exponent filings (%d LCA / %d PERM) across %d quarters",
             len(firm_rows), sum(1 for r in firm_rows if r['program'] == 'LCA'),
             sum(1 for r in firm_rows if r['program'] == 'PERM'), len(series))
