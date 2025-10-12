# 1) vervang psalms.py
cat > /root/bijbels-pastoraat-app/psalms.py <<'PY'
import re
import time
from typing import Dict
import httpx
from bs4 import BeautifulSoup
from config import settings

UA = "BijbelsPastoraatNL/1.0 (+https://gpt-harbers.duckdns.org)"

class PsalmboekClient:
    """Scraper leest /psalmen.php en extraheert verzen."""
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
        r = self._http.get(url)
        if r.status_code == 403:
            r = self._http.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.text

    def _extract_vers_map(self, html: str) -> Dict[int, str]:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.find(id="psalmkolom2") or soup
        verses: Dict[int, str] = {}
        for p in container.find_all("p"):
            title = ""
            strong = p.find("strong")
            if strong:
                a = strong.find("a")
                title = (a.get_text(strip=True) if a else strong.get_text(strip=True)).strip()
            if not title:
                title = (p.get_text(strip=True) or "").strip()
            m = re.match(r"(?i)^vers\s+(\d+)\b", title)
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

    def get_max_vers(self, psalm: int) -> int:
        key = ("max", psalm)
        item = self._cache.get(key)
        if item and time.time() - item[0] <= self.cache_seconds:
            return item[1]
        vmap = self._extract_vers_map(self._fetch_overview(psalm))
        maxv = max(vmap) if vmap else 1
        if self.cache_seconds > 0:
            self._cache[key] = (time.time(), maxv)
        return maxv

    def get_vers(self, psalm: int, vers: int) -> str:
        key = ("vers", psalm, vers)
        item = self._cache.get(key)
        if item and time.time() - item[0] <= self.cache_seconds:
            return item[1]
        vmap = self._extract_vers_map(self._fetch_overview(psalm))
        if vers not in vmap:
            raise ValueError(f"Vers {vers} niet gevonden voor psalm {psalm}.")
        text = vmap[vers]
        if self.cache_seconds > 0:
            self._cache[key] = (time.time(), text)
        return text

client = PsalmboekClient(
    base_url=str(settings.PSALM_SOURCE_BASE),
    berijming=settings.PSALM_BERIJMING,
    cache_seconds=settings.CACHE_SECONDS,
)
PY

# 2) rebuild ZONDER cache en herstart
cd /root/bijbels-pastoraat-app
docker build --no-cache -t bijbels-pastoraat:clean .
docker rm -f bijbels-pastoraat || true
docker run -d --name bijbels-pastoraat -p 8082:8000 --restart unless-stopped bijbels-pastoraat:clean

# 3) verifieer
docker logs --tail=50 -f bijbels-pastoraat
curl -sS http://127.0.0.1:8082/healthz
curl -sS "http://91.99.2.139:8082/api/psalm/max?psalm=1"
curl -sS "http://91.99.2.139:8082/api/psalm?psalm=1&vers=1"
