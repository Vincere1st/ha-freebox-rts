"""Coordinator polling the Freebox Home shutter nodes."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from freebox_api.exceptions import HttpRequestError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SHUTTER_CATEGORY

if TYPE_CHECKING:
    from homeassistant.components.freebox.router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

type FreeboxRtsConfigEntry = ConfigEntry[FreeboxRtsCoordinator]


class FreeboxRtsCoordinator(DataUpdateCoordinator[dict[Any, dict[str, Any]]]):
    """Fetch the shutter nodes through the router of the core Freebox entry."""

    config_entry: FreeboxRtsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FreeboxRtsConfigEntry,
        core_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._core_entry = core_entry

    @property
    def router(self) -> FreeboxRouter:
        """Return the router of the core Freebox entry."""
        return self._core_entry.runtime_data

    async def _async_update_data(self) -> dict[Any, dict[str, Any]]:
        """Return the shutter nodes, keyed by node id."""
        if self._core_entry.state is not ConfigEntryState.LOADED:
            raise UpdateFailed("The Freebox integration is not loaded")
        try:
            nodes = await self.router.home.get_home_nodes() or []
        except (HttpRequestError, ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error fetching Freebox Home nodes: {err!r}") from err
        return {node["id"]: node for node in nodes if node["category"] == SHUTTER_CATEGORY}
