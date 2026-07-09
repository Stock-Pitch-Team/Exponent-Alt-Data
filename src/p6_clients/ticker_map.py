"""Map revealed-client names to SEC tickers/CIKs, with an auditable trail."""
import json
import logging

from config import settings
from src.common import edgar, names

log = logging.getLogger(__name__)


def build_map(clients: list[dict], cutoff: float = 0.92) -> tuple[list[dict], list[dict]]:
    """Return (matched, unmatched). Ambiguous names go to unmatched, never guessed."""
    tickers = edgar.all_tickers()
    by_norm: dict[str, list] = {}
    for t, entry in tickers.items():
        by_norm.setdefault(names.normalize_company(entry["title"]), []).append(entry)

    matched, unmatched = [], []
    norm_keys = list(by_norm.keys())
    for client in clients:
        norm = names.normalize_company(client["name"])
        candidates = by_norm.get(norm)
        method, score = "exact", 1.0
        if not candidates:
            hit = names.best_match(norm, norm_keys, cutoff=cutoff)
            if hit:
                candidates, score, method = by_norm[hit[0]], hit[1], "fuzzy"
        if not candidates:
            unmatched.append({**client, "reason": "no SEC name match"})
            continue
        # multiple share classes of the same company are fine; different CIKs are ambiguity
        ciks = {c["cik_str"] for c in candidates}
        if len(ciks) > 1:
            unmatched.append({**client, "reason": "ambiguous: multiple CIKs",
                              "candidates": [c["title"] for c in candidates][:4]})
            continue
        entry = candidates[0]
        matched.append({**client, "ticker": entry["ticker"], "cik": entry["cik_str"],
                        "sec_title": entry["title"], "match_method": method,
                        "match_score": round(score, 3)})
    (settings.INTERIM_DIR / "p6_ticker_map.json").write_text(
        json.dumps({"matched": matched, "unmatched": unmatched}, indent=1),
        encoding="utf-8")
    log.info("ticker map: %d matched, %d unmatched", len(matched), len(unmatched))
    return matched, unmatched
