"""Freebox RTS shutters, an add-on for the core Freebox integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CORE_DOMAIN
from .coordinator import FreeboxRtsConfigEntry, FreeboxRtsCoordinator

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: FreeboxRtsConfigEntry) -> bool:
    """Set up Freebox RTS shutters."""
    core_entry = next(
        (
            e
            for e in hass.config_entries.async_entries(CORE_DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ),
        None,
    )
    if core_entry is None:
        raise ConfigEntryNotReady("The Freebox integration is not loaded yet")

    coordinator = FreeboxRtsCoordinator(hass, entry, core_entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreeboxRtsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
