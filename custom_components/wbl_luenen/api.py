"""Client for the WBL Lünen waste calendar (wbl.de).

WBL publishes one iCal file per street and year:
https://wbl.de/pdf/ical<year>.php?strasse=<street>&no_...=0
The street list comes from the <select> on the "Abfuhrtermine <year>" page.
A collection day can cover several bins, e.g. SUMMARY "Graue-Tonne,Bio-Tonne".
"""

from __future__ import annotations

from datetime import date
import html
import re
import unicodedata

import aiohttp

PAGE_URL = "https://wbl.de/abfallentsorgung/abfuhrtermine-{year}"
ICAL_URL = "https://wbl.de/pdf/ical{year}.php"
TIMEOUT = aiohttp.ClientTimeout(total=30)

# Request every bin; filtering happens in Home Assistant.
ALL_BINS_PARAMS = {
    name: "0"
    for name in (
        "no_behaelter_14",
        "no_container_14",
        "no_behaelter_4",
        "no_container_4",
        "no_gelb",
        "no_gelb_container",
        "no_bio",
        "no_papier",
        "no_papier_container",
    )
}

# iCal names -> display names
BIN_NAMES = {
    "Graue-Tonne": "Graue Tonne",
    "Rote-Tonne": "Rote Tonne",
    "Container-Grau": "Grauer Container",
    "Container-Rot": "Roter Container",
    "Gelbe-Tonne": "Gelbe Tonne",
    "Gelber-Container": "Gelber Container",
    "Bio-Tonne": "Bio-Tonne",
    "Blaue-Tonne": "Blaue Tonne",
    "Blauer-Container": "Blauer Container",
    "Weihnachtsbaum": "Weihnachtsbaum",
}

_SELECT_RE = re.compile(r'<select[^>]*name="strasse"[^>]*>(.*?)</select>', re.I | re.S)
_OPTION_RE = re.compile(r'<option[^>]*value="([^"]+)"', re.I)
_EVENT_RE = re.compile(r"BEGIN:VEVENT(.*?)END:VEVENT", re.S)
_DTSTART_RE = re.compile(r"^DTSTART[^:]*:(\d{4})(\d{2})(\d{2})", re.M)
_SUMMARY_RE = re.compile(r"^SUMMARY[^:]*:(.*)$", re.M)


class WblError(Exception):
    """Base error."""


class WblConnectionError(WblError):
    """wbl.de not reachable or returned an unexpected page."""


def normalize(text: str) -> str:
    """Normalize street names so user input matches WBL spelling."""
    text = unicodedata.normalize("NFC", html.unescape(text)).strip().lower()
    text = text.replace("ß", "ss")
    text = re.sub(r"(str\.|strasse)(?=\s|$)", "str", text)
    return re.sub(r"\s+", " ", text)


def parse_ical(text: str) -> dict[str, list[date]]:
    """Return {bin key: sorted dates} from a WBL iCal file."""
    text = text.replace("\r\n", "\n").replace("\n ", "")
    result: dict[str, set[date]] = {}
    for event in _EVENT_RE.findall(text):
        start = _DTSTART_RE.search(event)
        summary = _SUMMARY_RE.search(event)
        if not start or not summary:
            continue
        day = date(int(start.group(1)), int(start.group(2)), int(start.group(3)))
        for key in summary.group(1).replace("\\,", ",").split(","):
            if key := key.strip():
                result.setdefault(key, set()).add(day)
    return {key: sorted(days) for key, days in result.items()}


def bin_name(key: str) -> str:
    return BIN_NAMES.get(key, key.replace("-", " "))


class WblClient:
    """Reads streets and collection dates from wbl.de."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, url: str, **params: str) -> tuple[int, str]:
        try:
            async with self._session.get(url, params=params, timeout=TIMEOUT) as resp:
                return resp.status, await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WblConnectionError(str(err)) from err

    async def streets(self, year: int) -> list[str]:
        """All street names WBL knows (falls back to the previous year's page)."""
        for page_year in (year, year - 1):
            status, page = await self._get(PAGE_URL.format(year=page_year))
            match = _SELECT_RE.search(page) if status == 200 else None
            if match:
                return [html.unescape(v) for v in _OPTION_RE.findall(match.group(1))]
        raise WblConnectionError("Street list not found on wbl.de")

    async def search_streets(self, query: str, year: int) -> list[str]:
        """Streets matching the user input; exact matches first.

        Long streets are split by house numbers ("Ahornstraße 1-13 und 2-18"),
        so a query matches every entry that starts with the street name.
        """
        wanted = normalize(query)
        exact: list[str] = []
        prefix: list[str] = []
        partial: list[str] = []
        for street in await self.streets(year):
            norm = normalize(street)
            if norm == wanted:
                exact.append(street)
            elif norm.startswith(wanted + " "):
                prefix.append(street)
            elif wanted in norm:
                partial.append(street)
        if exact and not prefix:
            return exact
        return exact + prefix or partial

    async def fetch(self, street: str, year: int) -> dict[str, list[date]]:
        """Dates for one street: this year's file, plus next year's once published."""
        result: dict[str, list[date]] = {}
        for ical_year in (year, year + 1):
            status, text = await self._get(
                ICAL_URL.format(year=ical_year), strasse=street, **ALL_BINS_PARAMS
            )
            if status != 200 or "BEGIN:VCALENDAR" not in text:
                if ical_year == year:
                    raise WblConnectionError(f"No calendar for {ical_year}")
                continue
            for key, days in parse_ical(text).items():
                result[key] = sorted(set(result.get(key, [])) | set(days))
        return result
