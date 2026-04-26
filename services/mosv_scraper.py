from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

_MONTHS_BG = {
    1: "yanuari", 2: "fevruari", 3: "mart", 4: "april",
    5: "maj", 6: "yuni", 7: "yuli", 8: "avgust",
    9: "septemvri", 10: "oktomvri", 11: "noemvri", 12: "dekemvri",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "bg,en;q=0.9",
    "Referer": "https://www.moew.government.bg/",
}


class MosvScraperService:
    def __init__(self, cfg):
        self._base_url = cfg.base_url
        self._bulletins_dir = Path(cfg.bulletins_dir)
        self._request_timeout = cfg.request_timeout
        self._download_timeout = cfg.download_timeout

    def download_bulletin(
        self, d: date, session: requests.Session, force: bool = False
    ) -> tuple[Path, str] | None:
        if not force:
            cached = self._existing_bulletin(d)
            if cached:
                print(f"  [cached] {cached.name}")
                return cached, cached.suffix.lstrip(".")

        soup = self._fetch_page(d, session)
        if soup is None:
            return None

        attachment = self._find_attachment(soup)
        if attachment is None:
            print("  No attachment link found on page.")
            return None

        url, ext = attachment
        print(f"  Found {ext.upper()} → {url}")

        try:
            r = session.get(url, timeout=self._download_timeout)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  Download failed: {e}")
            return None

        self._bulletins_dir.mkdir(parents=True, exist_ok=True)
        path = self._bulletins_dir / f"{d.isoformat()}.{ext}"
        path.write_bytes(r.content)
        print(f"  Saved → {path.name} ({len(r.content):,} bytes)")
        return path, ext

    def _fetch_page(self, d: date, session: requests.Session) -> BeautifulSoup | None:
        for pad in (True, False):
            url = self._build_url(d, pad_day=pad)
            try:
                r = session.get(url, timeout=self._request_timeout)
                if r.status_code == 200:
                    return BeautifulSoup(r.text, "html.parser")
            except requests.RequestException:
                continue
        return None

    def _find_attachment(self, soup: BeautifulSoup) -> tuple[str, str] | None:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            lower = href.lower()
            if lower.endswith(".docx"):
                ext = "docx"
            elif lower.endswith(".doc"):
                ext = "doc"
            elif lower.endswith(".pdf"):
                ext = "pdf"
            else:
                continue
            full = href if href.startswith("http") else self._base_url + href
            return full, ext
        return None

    def _build_url(self, d: date, pad_day: bool = True) -> str:
        day = str(d.day).zfill(2) if pad_day else str(d.day)
        month = _MONTHS_BG[d.month]
        return (
            f"{self._base_url}/bg/ejedneven-byuletin-za-sustoyanieto-"
            f"na-vodite-za-{day}-{month}-{d.year}-g/"
        )

    def _existing_bulletin(self, d: date) -> Path | None:
        for ext in ("docx", "doc", "pdf"):
            path = self._bulletins_dir / f"{d.isoformat()}.{ext}"
            if path.exists() and path.stat().st_size > 0:
                return path
        return None
