"""Cached, rate-limited, retrying HTTP layer shared by all pipelines.

Every fetch goes through cached_get / cached_post_json. On repeated failure
raises SourceUnavailable, which pipeline build steps convert into an honest
'partial'/'unavailable' output status. Nothing here ever fabricates data.
"""
import logging
import random
import time
from urllib.parse import urlsplit

import requests

from config import settings
from src.common import cache

log = logging.getLogger(__name__)

_last_request_at: dict[str, float] = {}
_session = requests.Session()


class SourceUnavailable(Exception):
    """Raised when a source cannot be fetched after retries."""

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"{url}: {reason}")


def _throttle(url: str):
    host = urlsplit(url).netloc.lower()
    min_gap = settings.RATE_LIMITS.get(host, settings.DEFAULT_RATE_LIMIT)
    last = _last_request_at.get(host)
    if last is not None:
        wait = min_gap - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request_at[host] = time.time()


def _request_with_retries(method: str, url: str, *, params=None, json_body=None,
                          headers=None, stream=False):
    hdrs = {"User-Agent": settings.USER_AGENT}
    if headers:
        hdrs.update(headers)
    last_reason = "unknown"
    for attempt in range(settings.MAX_RETRIES):
        _throttle(url)
        try:
            resp = _session.request(
                method, url, params=params, json=json_body, headers=hdrs,
                timeout=settings.REQUEST_TIMEOUT, stream=stream,
            )
        except requests.RequestException as exc:
            last_reason = f"connection error: {exc.__class__.__name__}"
            log.warning("attempt %d %s %s -> %s", attempt + 1, method, url, last_reason)
        else:
            if resp.status_code < 400:
                return resp
            if resp.status_code in (429, 500, 502, 503, 504):
                last_reason = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After")
                log.warning("HTTP %d from %s (Retry-After: %s)",
                            resp.status_code, urlsplit(url).netloc, retry_after)
                if retry_after:
                    try:
                        time.sleep(min(float(retry_after), 300))
                        continue
                    except ValueError:
                        pass
            else:
                raise SourceUnavailable(url, f"HTTP {resp.status_code}")
        time.sleep(settings.BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 1))
    raise SourceUnavailable(url, last_reason)


def cached_get(url: str, *, params=None, headers=None, ttl_days=settings.TTL_API,
               use_cache=True) -> bytes:
    key = cache.cache_key("GET", url, params)
    if use_cache:
        hit = cache.get(key)
        if hit is not None:
            return hit[0]
    resp = _request_with_retries("GET", url, params=params, headers=headers)
    payload = resp.content
    cache.put(key, payload, resp.url, ttl_days, resp.status_code)
    return payload


def cached_post_json(url: str, json_body, *, headers=None, ttl_days=settings.TTL_API,
                     use_cache=True) -> bytes:
    key = cache.cache_key("POST", url, body=json_body)
    if use_cache:
        hit = cache.get(key)
        if hit is not None:
            return hit[0]
    resp = _request_with_retries("POST", url, json_body=json_body, headers=headers)
    payload = resp.content
    cache.put(key, payload, url, ttl_days, resp.status_code)
    return payload


def download_file(url: str, dest_path, *, expected_min_bytes=1024) -> dict:
    """Download a (possibly large) file to disk with streaming. Skips if present."""
    dest_path = str(dest_path)
    import os
    if os.path.exists(dest_path) and os.path.getsize(dest_path) >= expected_min_bytes:
        return {"path": dest_path, "size_bytes": os.path.getsize(dest_path), "cached": True}
    resp = _request_with_retries("GET", url, stream=True)
    tmp = dest_path + ".part"
    size = 0
    with open(tmp, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            fh.write(chunk)
            size += len(chunk)
    if size < expected_min_bytes:
        raise SourceUnavailable(url, f"downloaded only {size} bytes")
    os.replace(tmp, dest_path)
    return {"path": dest_path, "size_bytes": size, "cached": False}
