"""Shared HTTP session with retries and back-off for public APIs."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "fabric-lakehouse-food-prices/0.1 (+https://github.com/alejandrocaldentey/fabric-lakehouse-food-prices)"


def build_session(total_retries: int = 5, backoff_factor: float = 1.0) -> requests.Session:
    """Return a session that retries on 429 and 5xx with exponential back-off."""
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session
