import re
import time
import random
from typing import Optional, Dict, Tuple, List

import httpx
from bs4 import BeautifulSoup
from config import settings

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

class PsalmboekClient:
    """
    Huidige PHP-structuur van psalmboek.nl:
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

    def _psalm_overview_url(self, psalm: int) -> str:
        return f"{self.base_url}/psalmen.php?berijming={self.berijming}&psalm={psalm}"

    def _vers_url(self, psalm: int, vers: int) -> str:
        return f"{self.base_url}/psalm.php?berijming={self.berijming}&psalm={psalm}&vers={vers}"

    def _get_html(self, url: str) -> str:
        r = self._client.get(url)
        if r.status_code == 403:
            self._client.headers["User-Agent"] = random.choice(UA_POOL)
            r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def get_max_vers(self, psalm: int) -> int:
        cache_key = ("max", psalm)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return int(cached)

        html = self._get_html(self._psalm_overview_url(psalm))
        soup = BeautifulSoup(html, "html.parser")

        candidates: List[int] = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.search(r"[?&]vers=(\d+)\b", href)
            if m:
                candidates.append(int(m.group(1)))
            txt = (a.get_text() or "").strip()
            m2 = re.fullmatch(r"[Vv]ers\s+(\d+)", txt)
            if m2:
                candidates.append(int(m2.group(1)))

        for li in soup.find_all("li"):
            txt = (li.get_text() or "").strip()
            m = re.search(r"[Vv]ers\s+(\d+)", txt)
            if m:
                candidates.append(int(m.group(1)))

        for m in re.finditer(r"[?&]vers=(\d+)\b", html):
            candidates.append(int(m.group(1)))

        max_vers = max(candidates) if candidates else 1
        self._cache_set(cache_key, max_vers)
        return max_vers

    def get_vers(self, psalm: int, vers: int) -> str:
        cache_key = ("vers", psalm, vers)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return str(cached)

        html = self._get_html(self._vers_url(psalm, vers))
        soup = BeautifulSoup(html, "html.parser")

        selectors = [
            "#psalmtekst",
            "div.verse",
            "div.strofe",
            "article.verse",
            "section.verse",
            "div.content",
            "main",
            "article",
        ]

        text_lines: List[str] = []
        found = False
        for sel in selectors:
            for container in soup.select(sel):
                raw = container.get_text("\n").strip()
                if raw and len(raw) > 10:
                    candidate = [ln.rstrip() for ln in raw.splitlines()]
                    candidate = [ln for ln in candidate if ln.strip()]
                    if candidate:
                        text_lines = candidate
                        found = True
                        break
            if found:
                break

        if not found:
            body = soup.get_text("\n").strip()
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            text_lines = lines[:12] if lines else []

        if not text_lines:
            raise ValueError("Kon versregel niet betrouwbaar extraheren uit psalmboek.nl.")

        verse_text = "\n".join(text_lines).strip()
        verse_text = re.sub(r"\n{3,}", "\n\n", verse_text)

        self._cache_set(cache_key, verse_text)
        return verse_text

client = PsalmboekClient(
    base_url=str(settings.PSALM_SOURCE_BASE),
    berijming=settings.PSALM_BERIJMING,
    cache_seconds=settings.CACHE_SECONDS,
)
