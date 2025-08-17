import re
import time
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from .config import settings


class PsalmboekClient:
    """
    Client die psalmboek.nl (berijming 1773) benadert en versregels/max-vers ophaalt.
    Parser is defensief opgezet i.v.m. mogelijke HTML-variaties.
    """

    def __init__(self, base_url: str, berijming: str, cache_seconds: int = 0):
        self.base_url = base_url.rstrip("/")
        self.berijming = berijming
        self.cache_seconds = max(0, cache_seconds)
        # Eenvoudige in-memory cache
        self._cache: dict[tuple, tuple[float, object]] = {}

        self._client = httpx.Client(
            timeout=httpx.Timeout(10.0, connect=10.0, read=10.0),
            headers={
                "User-Agent": "BijbelsPastoraatNL/1.0 (+https://example.local)"
            },
            follow_redirects=True,
        )

    def _cache_get(self, key: tuple) -> Optional[object]:
        if self.cache_seconds <= 0:
            return None
        item = self._cache.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts > self.cache_seconds:
            # verlopen
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: tuple, value: object) -> None:
        if self.cache_seconds <= 0:
            return
        self._cache[key] = (time.time(), value)

    def _psalm_url(self, psalm: int, vers: Optional[int] = None) -> str:
        # Voorbeelden op psalmboek.nl:
        # - Overzicht per psalm: /berijming/1773/psalm/1
        # - Specifiek vers:      /berijming/1773/psalm/1/1
        if vers is None:
            return f"{self.base_url}/berijming/{self.berijming}/psalm/{psalm}"
        return f"{self.base_url}/berijming/{self.berijming}/psalm/{psalm}/{vers}"

    def _get_html(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text

    def get_max_vers(self, psalm: int) -> int:
        """
        Bepaalt het maximale versnummer voor een psalm.
        Strategie:
        1) HTML ophalen van psalm-overzichtspagina
        2) Zoeken naar verwijzingen/knoppen naar verzen of een 'Vers X' lijst
        3) Val terug op heuristieken wanneer de structuur afwijkt
        """
        cache_key = ("max", psalm)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = self._psalm_url(psalm)
        html = self._get_html(url)
        soup = BeautifulSoup(html, "html.parser")

        candidates: list[int] = []

        # 1) Zoek links/knoppen die op losse verzen lijken
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # verwacht: .../psalm/<psalm>/<vers>
            m = re.search(rf"/psalm/{psalm}/(\d+)", href)
            if m:
                try:
                    candidates.append(int(m.group(1)))
                except ValueError:
                    pass

            # soms staat "Vers 5" als tekst
            txt = (a.get_text() or "").strip()
            m2 = re.fullmatch(r"[Vv]ers\s+(\d+)", txt)
            if m2:
                try:
                    candidates.append(int(m2.group(1)))
                except ValueError:
                    pass

        # 2) Zoek nummering in lijstelementen (bijv. <li>Vers 6</li>)
        for li in soup.find_all("li"):
            txt = (li.get_text() or "").strip()
            m = re.search(r"[Vv]ers\s+(\d+)", txt)
            if m:
                try:
                    candidates.append(int(m.group(1)))
                except ValueError:
                    pass

        # 3) Zoek data-attributes (fallback)
        for el in soup.find_all(attrs={"data-vers": True}):
            try:
                candidates.append(int(el["data-vers"]))
            except (ValueError, KeyError):
                pass

        if not candidates:
            # Zeer defensieve laatste poging: zoek '/psalm/<psalm>/<vers>' overal in de tekst
            for m in re.finditer(rf"/psalm/{psalm}/(\d+)", html):
                try:
                    candidates.append(int(m.group(1)))
                except ValueError:
                    pass

        if not candidates:
            # Als nog steeds niets: veilig falen met 1, caller kan 404 geven bij te hoog vers
            max_vers = 1
        else:
            max_vers = max(candidates)

        self._cache_set(cache_key, max_vers)
        return max_vers

    def get_vers(self, psalm: int, vers: int) -> str:
        """
        Haalt de exacte berijmde tekstregel van een psalmvers (1773).
        Strategie:
        1) HTML van specifieke verspagina
        2) Zoek naar blok(ken) die de regellijnen van dit vers dragen (div.class ~ 'verse' of 'strofe')
        3) Combineer regels met harde regeleinden
        """
        cache_key = ("vers", psalm, vers)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = self._psalm_url(psalm, vers)
        html = self._get_html(url)
        soup = BeautifulSoup(html, "html.parser")

        # mogelijke kandidaten voor het vers-blok
        selectors = [
            # veel sites gebruiken 'verse' of 'strofe' voor strofen
            "div.verse",
            "div.strofe",
            "article.verse",
            "section.verse",
            # generieker fallback: container met <br> regels
            "div.content",
            "main",
            "article",
        ]

        text_lines: list[str] = []

        found = False
        for sel in selectors:
            for container in soup.select(sel):
                # Heuristiek: haal alle tekstnodes en <br> geforceerd als nieuwe regels
                # We nemen alleen redelijk korte blokken (om volledige pagina te vermijden)
                raw = container.get_text("\n").strip()
                # Filter: verwacht meerdere regels; single-line blokken zijn vaak titels
                if raw and len(raw) > 10:
                    # Neem het eerste plausibele blok
                    candidate_lines = [ln.rstrip() for ln in raw.splitlines()]
                    # Filter lege staartkoppen
                    candidate_lines = [ln for ln in candidate_lines if ln.strip() != ""]
                    if candidate_lines:
                        text_lines = candidate_lines
                        found = True
                        break
            if found:
                break

        if not found:
            # Laatste fallback: pak body-tekst, maar probeer het versdeel tussen kopjes te isoleren
            body_text = soup.get_text("\n").strip()
            # Neem niet teveel: pak maximaal ~12 regels samenhangend als ruwe strofe
            lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
            text_lines = lines[:12] if lines else []

        # Finaliseren
        if not text_lines:
            raise ValueError("Kon versregel niet betrouwbaar extraheren uit psalmboek.nl.")

        # Combineer naar één string met harde regeleinden
        verse_text = "\n".join(text_lines).strip()

        # Minimalistische schoonmaak: collapse dubbele lege regels
        verse_text = re.sub(r"\n{3,}", "\n\n", verse_text)

        self._cache_set(cache_key, verse_text)
        return verse_text


client = PsalmboekClient(
    base_url=str(settings.PSALM_SOURCE_BASE),
    berijming=settings.PSALM_BERIJMING,
    cache_seconds=settings.CACHE_SECONDS,
)
