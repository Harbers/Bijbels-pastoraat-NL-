import re
import time
from typing import Dict

import httpx

from config import settings

UA = "BijbelsPastoraatNL/1.0 (+https://gpt-harbers.duckdns.org)"


class PsalmboekClient:
    """Scraper voor psalmboek.nl (berijming 1773) – leest alleen /psalmen.php."""

    def __init__(self, base_url: str, berijming: str, cache_seconds: int = 0):
        self.base_url = base_url.rstrip("/")
        self.berijming = berijming
        self.cache_seconds = max(0, cache_seconds)
        self._cache: Dict[tuple, tuple[float, object]] = {}
        self._http = httpx.Client(
            http2=True,
            headers={"User-Agent": UA},
            timeout=httpx.Timeout(15.0, connect=10.0, read=10.0),
            follow_redirects=True,
        )

    def _overview_url(self, psalm: int) -> str:
        return f"{self.base_url}/psalmen.php?berijming={self.berijming}&psalm={psalm}"

    def _fetch_overview(self, psalm: int) -> str:
        url = self._overview_url(psalm)
        response = self._http.get(url)
        if response.status_code == 403:
            response = self._http.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.text

    def _extract_vers_map(self, html: str) -> Dict[int, str]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        container = soup.find(id="psalmkolom2") or soup
        verses: Dict[int, str] = {}
        for p in container.find_all("p"):
            strong = p.find("strong")
            a = strong.find("a") if strong else None
            title = ""
            if a and a.get_text():
                title = a.get_text(strip=True)
            elif strong and strong.get_text():
                title = strong.get_text(strip=True)
            match = re.match(r"(?i)^vers\s+(\d+)\b", title)
            if not match:
                match = re.match(r"(?i)^vers\s+(\d+)\b", (p.get_text(strip=True) or ""))
            if not match:
                continue
            vers_num = int(match.group(1))
            raw = p.get_text(separator="\n", strip=True)
            raw = re.sub(rf"(?i)^\s*vers\s+{vers_num}\s*[:.]?\s*", "", raw).replace("\u00A0", " ").strip()
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            if lines:
                verses[vers_num] = "\n".join(lines)
        return verses

    def get_max_vers(self, psalm: int) -> int:
        cache_key = ("max", psalm)
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] <= self.cache_seconds:
            return cached[1]  # type: ignore[return-value]
        vers_map = self._extract_vers_map(self._fetch_overview(psalm))
        max_vers = max(vers_map) if vers_map else 1
        if self.cache_seconds > 0:
            self._cache[cache_key] = (time.time(), max_vers)
        return max_vers

    def get_vers(self, psalm: int, vers: int) -> str:
        cache_key = ("vers", psalm, vers)
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] <= self.cache_seconds:
            return cached[1]  # type: ignore[return-value]
        vers_map = self._extract_vers_map(self._fetch_overview(psalm))
        if vers not in vers_map:
            raise ValueError(f"Vers {vers} niet gevonden voor psalm {psalm}.")
        text = vers_map[vers]
        if self.cache_seconds > 0:
            self._cache[cache_key] = (time.time(), text)
        return text


client = PsalmboekClient(
    base_url=str(settings.PSALM_SOURCE_BASE),
    berijming=settings.PSALM_BERIJMING,
    cache_seconds=settings.CACHE_SECONDS,
)


def get_max_vers(psalm: int) -> int:
    return client.get_max_vers(psalm)


def get_vers(psalm: int, vers: int) -> str:
    return client.get_vers(psalm, vers)
