import re
import time
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup

from config import settings

UA = "BijbelsPastoraatNL/1.0 (+https://gpt-harbers.duckdns.org)"


class PsalmboekClient:
    """
    Haalt gegevens van de overzichtspagina:
      https://psalmboek.nl/psalmen.php?berijming=1773&psalm=<n>
    en extraheert daaruit de verzen.
    """

    def __init__(self, base_url: str, berijming: str, cache_seconds: int = 0) -> None:
        self.base_url = base_url.rstrip("/")
        self.berijming = berijming
        self.cache_seconds = max(0, cache_seconds)
        self._cache: Dict[tuple, tuple[float, object]] = {}

        self._http = httpx.Client(
            http2=True,
            timeout=httpx.Timeout(15.0, connect=10.0, read=10.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        )

    # ---- helpers -------------------------------------------------------------

    def _overview_url(self, psalm: int) -> str:
        return f"{self.base_url}/psalmen.php?berijming={self.berijming}&psalm={psalm}"

    def _get_html(self, url: str) -> str:
        r = self._http.get(url)
        if r.status_code == 403:  # simpele UA-fallback
            r = self._http.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.text

    # ---- caching -------------------------------------------------------------

    def _cache_get(self, key: tuple) -> Optional[object]:
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

    def _cache_set(self, key: tuple, value: object) -> None:
        if self.cache_seconds > 0:
            self._cache[key] = (time.time(), value)

    # ---- parsing -------------------------------------------------------------

    def _extract_vers_map(self, html: str) -> Dict[int, str]:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.find(id="psalmkolom2") or soup

        verses: Dict[int, str] = {}
        for p in container.find_all("p"):
            strong = p.find("strong")
            a = strong.find("a") if strong else None

            title = (
                (a.get_text(strip=True) if a else None)
                or (strong.get_text(strip=True) if strong else "")
            ).strip()

            m = re.match(r"(?i)^vers\s+(\d+)\b", title) or re.match(
                r"(?i)^vers\s+(\d+)\b", (p.get_text(strip=True) or "")
            )
            if not m:
                continue

            v = int(m.group(1))
            raw = p.get_text(separator="\n", strip=True)
            raw = re.sub(rf"(?i)^\s*vers\s+{v}\s*[:.]?\s*", "", raw)
            raw = raw.replace("\u00A0", " ").strip()
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            if lines:
                verses[v] = "\n".join(lines)

        return verses

    # ---- public API ----------------------------------------------------------

    def get_max_vers(self, psalm: int) -> int:
        key = ("max", psalm)
        cached = self._cache_get(key)
        if cached is not None:
            return int(cached)

        html = self._get_html(self._overview_url(psalm))
        vmap = self._extract_vers_map(html)
        maxv = max(vmap) if vmap else 1
        self._cache_set(key, maxv)
        return maxv

    def get_vers(self, psalm: int, vers: int) -> str:
        key = ("vers", psalm, vers)
        cached = self._cache_get(key)
        if cached is not None:
            return str(cached)

        html = self._get_html(self._overview_url(psalm))
        vmap = self._extract_vers_map(html)
        if vers not in vmap:
            raise ValueError(f"Vers {vers} niet gevonden voor psalm {psalm}.")
        text = vmap[vers]
        self._cache_set(key, text)
        return text


client = PsalmboekClient(
    base_url=str(settings.PSALM_SOURCE_BASE),
    berijming=settings.PSALM_BERIJMING,
    cache_seconds=settings.CACHE_SECONDS,
)
