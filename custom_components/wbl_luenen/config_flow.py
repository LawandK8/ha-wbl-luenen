"""Config flow: the user types only the street, then ticks their bins.

Long streets are split by house numbers on wbl.de ("Ahornstraße 1-13 und
2-18"); then the flow offers a dropdown to pick the right part.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .api import WblClient, WblConnectionError, bin_name, normalize
from .const import CONF_BINS, CONF_STREET, DEFAULT_BINS, DOMAIN


def _bins_schema(available: list[str], selected: list[str]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_BINS, default=[b for b in selected if b in available]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=b, label=bin_name(b)) for b in available
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
    )


class WblConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one street."""

    VERSION = 1

    def __init__(self) -> None:
        self._streets: list[str] = []
        self._street = ""
        self._available: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WblOptionsFlow:
        return WblOptionsFlow()

    def _client(self) -> WblClient:
        return WblClient(async_get_clientsession(self.hass))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._streets = await self._client().search_streets(
                    user_input[CONF_STREET], dt_util.now().year
                )
            except WblConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if not self._streets:
                    errors[CONF_STREET] = "street_not_found"
                elif len(self._streets) == 1:
                    return await self._select_street(self._streets[0])
                else:
                    return await self.async_step_street()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_STREET): str}), user_input
            ),
            errors=errors,
        )

    async def async_step_street(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Several streets (or street parts) matched the input."""
        if user_input is not None:
            return await self._select_street(user_input[CONF_STREET])
        return self.async_show_form(
            step_id="street",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STREET): SelectSelector(
                        SelectSelectorConfig(
                            options=self._streets, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def _select_street(self, street: str) -> ConfigFlowResult:
        self._street = street
        await self.async_set_unique_id(normalize(street))
        self._abort_if_unique_id_configured()
        try:
            data = await self._client().fetch(street, dt_util.now().year)
        except WblConnectionError:
            return self.async_abort(reason="cannot_connect")
        if not data:
            return self.async_abort(reason="no_dates")
        self._available = list(data)
        return await self.async_step_bins()

    async def async_step_bins(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the bins this household actually has."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_BINS]:
                return self.async_create_entry(
                    title=self._street,
                    data={CONF_STREET: self._street},
                    options={CONF_BINS: user_input[CONF_BINS]},
                )
            errors["base"] = "no_bins"
        return self.async_show_form(
            step_id="bins",
            data_schema=_bins_schema(self._available, DEFAULT_BINS),
            description_placeholders={"street": self._street},
            errors=errors,
        )


class WblOptionsFlow(OptionsFlow):
    """Change the selected bins later."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_BINS]:
                return self.async_create_entry(data=user_input)
            errors["base"] = "no_bins"
        try:
            data = await WblClient(async_get_clientsession(self.hass)).fetch(
                self.config_entry.data[CONF_STREET], dt_util.now().year
            )
        except WblConnectionError:
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(
            step_id="init",
            data_schema=_bins_schema(
                list(data), self.config_entry.options.get(CONF_BINS, DEFAULT_BINS)
            ),
            errors=errors,
        )
