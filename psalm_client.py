import re
import time
import random
from typing import Optional, Dict, Tuple, List

import httpx
from bs4 import BeautifulSoup
from .config import settings

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


class PsalmboekClient:
    """
    Client voor psalmboek.nl – gebruikt de huidige PHP-structuur:
      - Overzicht psalm:  /psalmen.php?berijming=1773&psalm=<n>
      - Specifiek vers:   /psalm.php?berijming=1773&psalm=<n>&vers=<m>
    Parser is defensief i.v.m. HTML-variaties.
    """

    def __init__(self, base_url: str, berijming: str, cache_seconds: int = 0):
        self.base_url = base_url.rstrip("/")
        self.berijming = berijming
        self.cache_seconds = max(0, cache_seconds)
        self._cache: Dict[Tuple, Tuple[float, object]] = {}

        self._client = httpx.Client(
            http2=True,
            timeout=httpx.Timeout(15.0, connect=10.0, read=10.0),
            headers={
                "User-Agent": random.choice(UA_POOL),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Connection": "keep-alive",
            },
            follow_redirects=True,
        )

    # --------- cache ----------
    def _cache_get(self, key: Tuple) -> Optional[object]:
        if self.cache_seconds <= 0:
            return None
        item = self._cache.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts > self.cache_seconds:
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: Tuple, value: object) -> None:
        if self.cache_seconds > 0:
            self._cache[key] = (time.time(), value)

    # --------- urls ----------
    def _psalm_overview_url(self, psalm: int) -> str:
        return f"{self.base_url}/psalmen.php?berijming={self.berijming}&psalm={psalm}"

    def _vers_url(self, psalm: int, vers: int)
