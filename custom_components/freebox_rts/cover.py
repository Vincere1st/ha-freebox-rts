"""Cover platform: Freebox RTS shutters."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from freebox_api.exceptions import HttpRequestError

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CORE_DOMAIN
from .coordinator import FreeboxRtsConfigEntry, FreeboxRtsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxRtsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the shutters, including the ones discovered later."""
    coordinator = entry.runtime_data
    known: set[Any] = set()

    @callback
    def _add_new() -> None:
        new_ids = [node_id for node_id in coordinator.data if node_id not in known]
        if not new_ids:
            return
        known.update(new_ids)
        async_add_entities(FreeboxRtsCover(coordinator, node_id) for node_id in new_ids)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class FreeboxRtsCover(CoordinatorEntity[FreeboxRtsCoordinator], CoverEntity):
    """A Freebox Home shutter node."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, coordinator: FreeboxRtsCoordinator, node_id: Any) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)
        self._node_id = node_id
        node = coordinator.data[node_id]
        router = coordinator.router

        # Same unique_id and device identifiers as the former patched core integration
        self._attr_unique_id = f"{router.mac}-node_{node_id}"

        manufacturer, model = "Freebox SAS", None
        if node["type"].get("inherit") == "node::rts":
            manufacturer, model = "Somfy", "RTS"
        self._attr_device_info = DeviceInfo(
            identifiers={(CORE_DOMAIN, node_id)},
            manufacturer=manufacturer,
            model=model,
            name=node["label"].strip(),
            via_device=(CORE_DOMAIN, router.mac),
        )

        # Optimistic state set by a command, dropped at the next refresh
        self._has_optimistic = False
        self._optimistic_closed: bool | None = None

    @property
    def _node(self) -> dict[str, Any] | None:
        return self.coordinator.data.get(self._node_id)

    @property
    def available(self) -> bool:
        """Return if the node is still reported by the Freebox."""
        return super().available and self._node is not None

    def _endpoint(self, ep_type: str, name: str) -> dict[str, Any] | None:
        node = self._node
        if node is None:
            return None
        return next(
            (
                ep
                for ep in node["show_endpoints"]
                if ep["name"] == name and ep["ep_type"] == ep_type
            ),
            None,
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._has_optimistic:
            return self._optimistic_closed
        endpoint = self._endpoint("signal", "state")
        if endpoint is None or endpoint.get("value") is None:
            return None
        return bool(endpoint["value"])

    @callback
    def _handle_coordinator_update(self) -> None:
        self._has_optimistic = False
        super()._handle_coordinator_update()

    async def _async_command(self, name: str, closed: bool | None) -> None:
        endpoint = self._endpoint("slot", name)
        if endpoint is None:
            raise HomeAssistantError(f"The shutter has no '{name}' command")
        try:
            await self.coordinator.router.home.set_home_endpoint_value(
                self._node_id, endpoint["id"], {"value": True}
            )
        except (HttpRequestError, ClientError, TimeoutError) as err:
            raise HomeAssistantError(f"Freebox command '{name}' failed: {err!r}") from err
        self._has_optimistic = True
        self._optimistic_closed = closed
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._async_command("up", False)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._async_command("down", True)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._async_command("stop", None)
