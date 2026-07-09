"""Central paths, rate limits, and retry policy for all pipelines."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
INTERIM_DIR = DATA_DIR / "interim"
SITE_DATA_DIR = DATA_DIR / "site"
SITE_DIR = PROJECT_ROOT / "site"
EXPLAINERS_DIR = PROJECT_ROOT / "content" / "explainers"
LOGS_DIR = PROJECT_ROOT / "logs"

for _d in (RAW_DIR, CACHE_DIR, INTERIM_DIR, SITE_DATA_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "")
REGULATIONS_GOV_API_KEY = os.getenv("REGULATIONS_GOV_API_KEY", "")
COURTLISTENER_API_TOKEN = os.getenv("COURTLISTENER_API_TOKEN", "")
OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY", "")

USER_AGENT = f"EXPO-altdata-research/0.1 ({CONTACT_EMAIL})"

# Minimum seconds between requests, per domain. Domains not listed default to 1.0s.
RATE_LIMITS = {
    "data.sec.gov": 0.15,
    "www.sec.gov": 0.15,
    "api.openalex.org": 0.15,
    "web.archive.org": 1.3,
    "www.exponent.com": 10.0,  # robots.txt Crawl-delay: 10
    "api.regulations.gov": 4.0,
    "api.usaspending.gov": 0.5,
    "api.fda.gov": 1.0,
    "static.nhtsa.gov": 1.0,
    "www.saferproducts.gov": 1.0,
    "www.courtlistener.com": 75.0,  # registered free tier: 50 requests/hour
    "www.jpml.uscourts.gov": 1.0,
}
DEFAULT_RATE_LIMIT = 1.0

MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2.0
REQUEST_TIMEOUT = 90

# Cache TTLs in days; None = never expires.
TTL_WAYBACK_PAYLOAD = None
TTL_LIVE_PAGE = 7
TTL_API = 30  # snapshot project: generous TTL so re-runs are free
