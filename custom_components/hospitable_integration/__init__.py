"""Hospitable Integration for Home Assistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HospitableApiClient, HospitableApiError
from .const import DOMAIN
from .coordinator import HospitableDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_POST_GUEST_MESSAGE = "post_guest_message"

SERVICE_POST_GUEST_MESSAGE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("reservation_uuid"): cv.string,
            vol.Required("message"): cv.string,
        }
    ),
    lambda value: _validate_post_guest_message_call(value),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hospitable Integration from a config entry."""
    api = HospitableApiClient(
        session=async_get_clientsession(hass),
        api_token=entry.data[CONF_API_TOKEN],
    )
    coordinator = HospitableDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    if not hass.services.has_service(DOMAIN, SERVICE_POST_GUEST_MESSAGE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_POST_GUEST_MESSAGE,
            _build_post_guest_message_handler(hass),
            schema=SERVICE_POST_GUEST_MESSAGE_SCHEMA,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Hospitable Integration config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_POST_GUEST_MESSAGE)

    return unload_ok


def _build_post_guest_message_handler(hass: HomeAssistant):
    async def async_post_guest_message(call: ServiceCall) -> None:
        reservation_uuid = call.data.get("reservation_uuid")
        entity_id = call.data.get("entity_id")
        message = call.data["message"].strip()
        if reservation_uuid is not None:
            reservation_uuid = reservation_uuid.strip()

        if entity_id and not reservation_uuid:
            state = hass.states.get(entity_id)
            if state is None:
                raise HomeAssistantError(f"Entity not found: {entity_id}")
            reservation_uuid = state.attributes.get("reservation_uuid")

        if not reservation_uuid:
            raise HomeAssistantError(
                "Provide reservation_uuid or an entity_id with a reservation_uuid attribute"
            )

        coordinator = _find_coordinator_for_reservation(hass, reservation_uuid)
        if coordinator is None:
            coordinators = list(hass.data.get(DOMAIN, {}).values())
            if not coordinators:
                raise HomeAssistantError("Hospitable Integration is not loaded")
            coordinator = coordinators[0]

        try:
            await coordinator.api.async_post_guest_message(reservation_uuid, message)
        except HospitableApiError as err:
            raise HomeAssistantError(
                f"Failed to post Hospitable guest message: {err}"
            ) from err

    return async_post_guest_message


def _validate_post_guest_message_call(value: dict) -> dict:
    """Validate that an automation message call targets one reservation source."""
    has_entity_id = bool(value.get("entity_id"))
    has_reservation_uuid = bool(str(value.get("reservation_uuid") or "").strip())
    if has_entity_id == has_reservation_uuid:
        raise vol.Invalid("Provide exactly one of entity_id or reservation_uuid")
    if not str(value.get("message") or "").strip():
        raise vol.Invalid("message must not be empty")
    return value


def _find_coordinator_for_reservation(
    hass: HomeAssistant, reservation_uuid: str
) -> HospitableDataUpdateCoordinator | None:
    """Find the coordinator whose cached reservations contain a reservation UUID."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        reservations: list[dict[str, Any]] = coordinator.data.get("reservations", [])
        if any(item.get("uuid") == reservation_uuid for item in reservations):
            return coordinator
    return None
