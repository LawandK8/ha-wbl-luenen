"""Data update coordinator for WBL Abfallkalender."""

from __future__ import annotations

from datetime import date
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import WblClient, WblError, bin_name
from .const import CONF_BINS, CONF_STREET, DEFAULT_BINS, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type WblConfigEntry = ConfigEntry[WblCoordinator]


class WblCoordinator(DataUpdateCoordinator[dict[str, list[date]]]):
    """Fetches the collection dates of the selected bins for one street."""

    config_entry: WblConfigEntry

    def __init__(self, hass: HomeAssistant, entry: WblConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self.street: str = entry.data[CONF_STREET]
        self.bins: list[str] = entry.options.get(CONF_BINS, DEFAULT_BINS)
        self.client = WblClient(async_get_clientsession(hass))
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"WBL Abfall {entry.title}",
            manufacturer="Wirtschaftsbetriebe Lünen GmbH",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://wbl.de/abfallentsorgung",
        )

    async def _async_update_data(self) -> dict[str, list[date]]:
        try:
            data = await self.client.fetch(self.street, dt_util.now().year)
        except WblError as err:
            raise UpdateFailed(f"WBL Abfallkalender: {err}") from err
        return {key: days for key, days in data.items() if key in self.bins}

    def upcoming(self, key: str) -> list[date]:
        """Collection dates from today on for one bin."""
        today = dt_util.now().date()
        return [d for d in self.data.get(key, []) if d >= today]

    @staticmethod
    def name_of(key: str) -> str:
        return bin_name(key)
