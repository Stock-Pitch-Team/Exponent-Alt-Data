"""File-based HTTP cache: sha256(method+url+params+body) -> payload + meta sidecar."""
import hashlib
import json
import time
from pathlib import Path

from config import settings


def cache_key(method: str, url: str, params=None, body=None) -> str:
    parts = [method.upper(), url]
    if params:
        parts.append(json.dumps(params, sort_keys=True, default=str))
    if body:
        parts.append(json.dumps(body, sort_keys=True, default=str))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _paths(key: str):
    d = settings.CACHE_DIR
    return d / f"{key}.bin", d / f"{key}.meta.json"


def get(key: str):
    """Return (bytes, meta) if cached and fresh, else None."""
    payload_p, meta_p = _paths(key)
    if not payload_p.exists() or not meta_p.exists():
        return None
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    ttl_days = meta.get("ttl_days")
    if ttl_days is not None:
        age_days = (time.time() - meta["fetched_at_epoch"]) / 86400
        if age_days > ttl_days:
            return None
    return payload_p.read_bytes(), meta


def put(key: str, payload: bytes, url: str, ttl_days, status_code: int):
    payload_p, meta_p = _paths(key)
    payload_p.write_bytes(payload)
    meta = {
        "url": url,
        "status_code": status_code,
        "fetched_at_epoch": time.time(),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ttl_days": ttl_days,
        "size_bytes": len(payload),
    }
    meta_p.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta
