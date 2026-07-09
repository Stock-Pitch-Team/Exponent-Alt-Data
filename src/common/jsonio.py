"""Atomic, envelope-enforcing JSON writer for data/site outputs."""
import json
import os

from config import settings

REQUIRED_META_FIELDS = (
    "pipeline", "output", "generated_at", "status", "status_reason",
    "sources", "coverage", "caveats", "methodology_id",
)


def write_site_json(filename: str, metadata: dict, data) -> str:
    for field in REQUIRED_META_FIELDS:
        if field not in metadata:
            raise ValueError(f"metadata missing required field: {field}")
    path = settings.SITE_DATA_DIR / filename
    tmp = str(path) + ".tmp"
    doc = {"metadata": metadata, "data": data}
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, path)
    return str(path)


def read_site_json(filename: str) -> dict:
    path = settings.SITE_DATA_DIR / filename
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
