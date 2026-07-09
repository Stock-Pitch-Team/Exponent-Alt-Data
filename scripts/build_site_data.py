"""Wrap data/site/*.json + content/explainers/*.json into file://-safe .data.js files.

fetch() of local JSON fails under file://, so every dataset is emitted as
   window.ALTDATA["<name>"] = {...};
and loaded with ordinary <script> tags. Fails the build if any chart id in
EXPECTED_EXPLAINERS lacks an explainer file — charts and their plain-English
methodology must ship together.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings  # noqa: E402

EXPECTED_EXPLAINERS = [
    "p1_headcount_timeseries", "p1_current_roster",
    "p2_litigation_timeseries", "p2_daubert", "p2_matched_cases",
    "p3_reactive_index", "p3_lag_overlay",
    "p4_publications", "p4_partners_rolling", "p4_collab_graph",
    "p5_federal_awards", "p5_regulatory_mentions",
    "p6_client_rnd", "p6_expo_financials",
]


def main():
    out_dir = settings.SITE_DIR / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    datasets = []
    for path in sorted(settings.SITE_DATA_DIR.glob("*.json")):
        name = path.stem
        doc = json.loads(path.read_text(encoding="utf-8"))
        js = f'window.ALTDATA = window.ALTDATA || {{}};\nwindow.ALTDATA[{json.dumps(name)}] = '
        js += json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + ";\n"
        (out_dir / f"{name}.data.js").write_text(js, encoding="utf-8")
        datasets.append({"name": name,
                         "status": doc.get("metadata", {}).get("status"),
                         "generated_at": doc.get("metadata", {}).get("generated_at")})

    explainers = {}
    missing = []
    for chart_id in EXPECTED_EXPLAINERS:
        p = settings.EXPLAINERS_DIR / f"{chart_id}.json"
        if not p.exists():
            missing.append(chart_id)
            continue
        explainers[chart_id] = json.loads(p.read_text(encoding="utf-8"))
    if missing:
        raise SystemExit(f"BUILD FAILED - missing explainers for: {', '.join(missing)}")

    js = ('window.ALTDATA = window.ALTDATA || {};\nwindow.ALTDATA["explainers"] = '
          + json.dumps(explainers, ensure_ascii=False, separators=(",", ":")) + ";\n")
    (out_dir / "explainers.data.js").write_text(js, encoding="utf-8")

    js = ('window.ALTDATA = window.ALTDATA || {};\nwindow.ALTDATA["manifest"] = '
          + json.dumps({"datasets": datasets}, separators=(",", ":")) + ";\n")
    (out_dir / "manifest.data.js").write_text(js, encoding="utf-8")
    print(f"wrote {len(datasets)} datasets + {len(explainers)} explainers -> {out_dir}")


if __name__ == "__main__":
    main()
