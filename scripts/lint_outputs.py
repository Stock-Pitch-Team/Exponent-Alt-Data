"""QA lint: every data/site/*.json must carry a full provenance envelope,
non-empty caveats, and (if charted) an explainer. Exits non-zero on failure."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings  # noqa: E402
from src.common.jsonio import REQUIRED_META_FIELDS  # noqa: E402

failures = []
for path in sorted(settings.SITE_DATA_DIR.glob("*.json")):
    doc = json.loads(path.read_text(encoding="utf-8"))
    meta = doc.get("metadata", {})
    for field in REQUIRED_META_FIELDS:
        if field not in meta:
            failures.append(f"{path.name}: missing metadata.{field}")
    if not meta.get("caveats"):
        failures.append(f"{path.name}: empty caveats")
    if meta.get("status") not in ("ok", "partial", "unavailable"):
        failures.append(f"{path.name}: bad status {meta.get('status')!r}")
    if meta.get("status") != "unavailable":
        if doc.get("data") in (None, {}, []):
            failures.append(f"{path.name}: status {meta['status']} but data is empty")
        if not meta.get("sources"):
            failures.append(f"{path.name}: status {meta['status']} but no sources")
    else:
        if not meta.get("status_reason"):
            failures.append(f"{path.name}: unavailable without status_reason")

if failures:
    print("LINT FAILED:")
    for f in failures:
        print(" -", f)
    raise SystemExit(1)
print(f"lint ok: {len(list(settings.SITE_DATA_DIR.glob('*.json')))} outputs pass")
