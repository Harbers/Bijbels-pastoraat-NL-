import re
import time
from typing import Optional, Dict, Tuple, List

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://psalmboek.nl"
CACHE_SECONDS = 600

class PsalmboekClient:
    """
    Parser voor psalmboek.nl
    Leest ALLE verzen vanaf: /psalmen.php?psalm=<n>  (bevat kopjes: 'Vers 1', 'Vers 2', ...)
    """

    def __init__(self, base_url: str, cache_seconds: int = 0):
        self.base_url = base_url.rstrip("/")
        self.cache_seconds = max(0, cache_seconds)
        self._cache: Dict[Tuple, Tuple[float, object]] = {}
        # http2 uit -> geen h2-dependency gedoe
        self._client = httpx.Client(
            http2=False,
            timeout=httpx.Timeout(15.0, connect=10.0, read=10.0),
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; BijbelsPastoraat/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        )

    def _cache_get(self, key: Tuple) -> Optional[object]:
        if self.cache_seconds <= 0: return None
        item = self._cache.get(key)
        if not item: return None
        ts, value = item
        if time.time() - ts > self.cache_seconds:
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: Tuple, value: object) -> None:
        if self.cache_seconds > 0:
            self._cache[key] = (time.time(), value)

    def _overview_url(self, psalm: int) -> str:
        # Deze pagina bevat alle verzen van de psalm
        return f"{self.base_url}/psalmen.php?psalm={psalm}"

    def _get_html(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def _extract_vers_blocks(self, html: str) -> List[str]:
        """
        Geeft een lijst tekstblokken: index 0 => Vers 1, index 1 => Vers 2, etc.
        We werken op plain text om zo min mogelijk van de HTML-structuur afhankelijk te zijn.
        """
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        text = re.sub(r"\r", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Vind alle posities van "Vers <nummer>"
        markers = [(m.start(), int(m.group(1))) for m in re.finditer(r"\bVers\s+(\d+)\b", text, flags=re.IGNORECASE)]
        if not markers:
            return []

        blocks: List[str] = []
        for idx, (start_pos, vers_num) in enumerate(markers):
            end_pos = markers[idx + 1][0] if idx + 1 < len(markers) else len(text)
            block = text[start_pos:end_pos].strip()

            # strip de kop "Vers X" zelf van het blok
            block = re.sub(rf"^\s*Vers\s+{vers_num}\s*", "", block, flags=re.IGNORECASE).strip()
            # normaliseer witregels
            block = re.sub(r"\n{3,}", "\n\n", block).strip()
            blocks.append(block)
        return blocks

    def get_max_vers(self, psalm: int) -> int:
        cache_key = ("max", psalm)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return int(cached)

        html = self._get_html(self._overview_url(psalm))
        blocks = self._extract_vers_blocks(html)
        max_vers = len(blocks) if blocks else 0
        self._cache_set(cache_key, max_vers)
        return max_vers

    def get_vers(self, psalm: int, vers: int) -> str:
        cache_key = ("vers", psalm, vers)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return str(cached)

        html = self._get_html(self._overview_url(psalm))
        blocks = self._extract_vers_blocks(html)
        if not blocks:
            raise ValueError("Kon geen verzen-paragrafen vinden op psalmoverzichtspagina.")

        if not (1 <= vers <= len(blocks)):
            raise ValueError(f"Gevraagd vers {vers} bestaat niet (gevonden {len(blocks)} verzen).")

        verse_text = blocks[vers - 1]
        self._cache_set(cache_key, verse_text)
        return verse_text

    def source_url(self, psalm: int, vers: Optional[int] = None) -> str:
        # We verwijzen naar de overzichtspagina als bron
        return self._overview_url(psalm)

client = PsalmboekClient(BASE_URL, CACHE_SECONDS)
