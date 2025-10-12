cat > /root/bijbels-pastoraat-app/psalms.py <<'PY'
import re, time
from typing import Optional, Dict, List
import httpx
from bs4 import BeautifulSoup
from config import settings

UA = "BijbelsPastoraatNL/1.0 (+https://gpt-harbers.duckdns.org)"

class PsalmboekClient:
    """
    Scraper voor berijmde psalmen (1773) op psalmboek.nl.
    Gebruikt alléén de overzichtspagina: /psalmen.php?berijming=1773&psalm=X
    """
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

    # ---------- cache ----------
    def _get_cache(self, key: tuple) -> Optional[object]:
        if self.cache_seconds <= 0: return None
        item = self._cache.get(key)
        if not item: return None
        ts, val = item
        if time.time() - ts > self.cache_seconds:
            self._cache.pop(key, None); return None
        return val

    def _set_cache(self, key: tuple, val: object) -> None:
        if self.cache_seconds > 0: self._cache[key] = (time.time(), val)

    # ---------- urls ----------
    def _overview_url(self, psalm: int) -> str:
        return f"{self.base_url}/psalmen.php?berijming={self.berijming}&psalm={psalm}"

    # ---------- fetch ----------
    def _fetch_overview(self, psalm: int) -> str:
        url = self._overview_url(psalm)
        r = self._http.get(url)
        if r.status_code == 403:
            r = self._http.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.text

    # ---------- parse ----------
    @staticmethod
    def _extract_vers_map(html: str) -> Dict[int, str]:
        """
        Retourneert {versnummer: 'regel1\\nregel2\\n...'} door <p>-blokken te parsen
        waarin 'Vers N' staat. Werkt tegen kleine HTML-variaties.
        """
        soup = BeautifulSoup(html, "html.parser")
        container = soup.find(id="psalmkolom2") or soup  # fallback

        verses: Dict[int, str] = {}
        for p in container.find_all("p"):
            strong = p.find("strong")
            a = strong.find("a") if strong else None
            title = (a.get_text(strip=True) if a else (strong.get_text(strip=True) if strong else "")).strip()
            m = re.match(r"(?i)^vers\s+(\d+)\b", title)
            if not m: 
                # soms staat 'Vers N' niet vet; probeer platte tekst
                m = re.match(r"(?i)^vers\s+(\d+)\b", (p.get_text(strip=True) or ""))
                if not m: 
                    continue
            vnum = int(m.group(1))

            raw = p.get_text(separator="\n", strip=True)
            raw = re.sub(rf"(?i)^\s*vers\s+{vnum}\s*[:.]?\s*", "", raw).strip()
            raw = raw.replace("\u00A0", " ")
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            if lines:
                verses[vnum] = "\n".join(lines)

        return verses

    # ---------- public api ----------
    def get_max_vers(self, psalm: int) -> int:
        key = ("max", psalm)
        cached = self._get_cache(key)
        if cached is not None: return cached
        html = self._fetch_overview(psalm)
        vmap = self._extract_vers_map(html)
        if not vmap: 
            return 1
        maxv = max(vmap.keys())
        self._set_cache(key, maxv)
        return maxv

    def get_vers(self, psalm: int, vers: int) -> str:
        key = ("vers", psalm, vers)
        cached = self._get_cache(key)
        if cached is not None: return cached
        html = self._fetch_overview(psalm)
        vmap = self._extract_vers_map(html)
        if vers not in vmap:
            raise ValueError(f"Vers {vers} niet gevonden voor psalm {psalm}.")
        txt = vmap[vers]
        self._set_cache(key, txt)
        return txt

client = PsalmboekClient(
    base_url=str(settings.PSALM_SOURCE_BASE),
    berijming=settings.PSALM_BERIJMING,
    cache_seconds=settings.CACHE_SECONDS,
)
PY
