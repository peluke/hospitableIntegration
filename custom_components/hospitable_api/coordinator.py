"""Data update coordinator for Hospitable API."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import HospitableApiClient, HospitableApiError
from .const import (
    CONF_LOOKAHEAD_DAYS,
    CONF_PROPERTY_UUIDS,
    DEFAULT_LOOKAHEAD_DAYS,
    DOMAIN,
    SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


class HospitableDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch Hospitable properties and reservations."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HospitableApiClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self.api = api
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        today = dt_util.now().date()
        lookahead_days = self.entry.data.get(CONF_LOOKAHEAD_DAYS, DEFAULT_LOOKAHEAD_DAYS)
        end_date = today + timedelta(days=lookahead_days)
        configured_property_uuids = _parse_property_uuids(
            self.entry.data.get(CONF_PROPERTY_UUIDS, "")
        )

        try:
            properties = await self.api.async_get_properties()
            normalized_properties = [_normalize_property(item) for item in properties]
            if configured_property_uuids:
                property_uuids = configured_property_uuids
                normalized_properties = [
                    item
                    for item in normalized_properties
                    if item["uuid"] in configured_property_uuids
                ]
            else:
                property_uuids = [
                    item["uuid"] for item in normalized_properties if item.get("uuid")
                ]
            if not property_uuids:
                raise UpdateFailed(
                    "No Hospitable property UUIDs found. Enter at least one property UUID in the integration options."
                )
            reservations = await self.api.async_get_reservations(
                start_date=today.isoformat(),
                end_date=end_date.isoformat(),
                date_query="checkin",
                property_uuids=property_uuids,
            )
            reservations.extend(
                await self.api.async_get_reservations(
                    start_date=today.isoformat(),
                    end_date=end_date.isoformat(),
                    date_query="checkout",
                    property_uuids=property_uuids,
                )
            )
            normalized_reservations = _dedupe_reservations(
                [_normalize_reservation(item) for item in reservations]
            )
            if configured_property_uuids:
                normalized_reservations = [
                    item
                    for item in normalized_reservations
                    if item.get("property_uuid") in configured_property_uuids
                ]
        except HospitableApiError as err:
            raise UpdateFailed(str(err)) from err

        return {
            "properties": normalized_properties,
            "reservations": normalized_reservations,
        }


def _parse_property_uuids(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _dedupe_reservations(reservations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for reservation in reservations:
        uuid = reservation.get("uuid")
        if uuid and uuid in seen:
            continue
        if uuid:
            seen.add(uuid)
        deduped.append(reservation)
    return deduped


def _normalize_property(item: dict[str, Any]) -> dict[str, Any]:
    attrs = _attributes(item)
    uuid = str(item.get("id") or item.get("uuid") or attrs.get("uuid") or "")
    return {
        "uuid": uuid,
        "name": attrs.get("name") or item.get("name") or uuid,
        "address": attrs.get("address") or item.get("address"),
        "raw": item,
    }


def _normalize_reservation(item: dict[str, Any]) -> dict[str, Any]:
    attrs = _attributes(item)
    guest = attrs.get("guest") or item.get("guest") or {}
    property_obj = (
        attrs.get("property") or attrs.get("properties") or item.get("property") or {}
    )
    property_uuid = (
        attrs.get("property_uuid")
        or item.get("property_uuid")
        or _relationship_id(item, "property")
        or _relationship_id(item, "properties")
        or property_obj.get("uuid")
        or property_obj.get("id")
    )
    uuid = str(item.get("id") or item.get("uuid") or attrs.get("uuid") or "")
    arrival = (
        attrs.get("arrival_date") or attrs.get("check_in") or item.get("arrival_date")
    )
    departure = (
        attrs.get("departure_date")
        or attrs.get("check_out")
        or item.get("departure_date")
    )

    return {
        "uuid": uuid,
        "code": attrs.get("code") or item.get("code"),
        "status": attrs.get("status") or item.get("status"),
        "platform": attrs.get("platform") or item.get("platform"),
        "arrival_date": arrival,
        "departure_date": departure,
        "guest_name": _guest_name(guest),
        "guest": guest,
        "property_uuid": str(property_uuid) if property_uuid else None,
        "property_name": (
            property_obj.get("name") if isinstance(property_obj, dict) else None
        ),
        "raw": item,
    }


def _attributes(item: dict[str, Any]) -> dict[str, Any]:
    attrs = item.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


def _relationship_id(item: dict[str, Any], relationship_name: str) -> str | None:
    relationships = item.get("relationships")
    if not isinstance(relationships, dict):
        return None
    relationship = relationships.get(relationship_name)
    if not isinstance(relationship, dict):
        return None
    data = relationship.get("data")
    if isinstance(data, dict):
        value = data.get("id") or data.get("uuid")
        return str(value) if value else None
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            value = first.get("id") or first.get("uuid")
            return str(value) if value else None
    return None


def _guest_name(guest: Any) -> str | None:
    if not isinstance(guest, dict):
        return None
    name = guest.get("name") or guest.get("full_name")
    if name:
        return str(name)
    first = guest.get("first_name")
    last = guest.get("last_name")
    full_name = " ".join(str(part) for part in (first, last) if part)
    return full_name or None
