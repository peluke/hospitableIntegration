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
                normalized_properties = [
                    item
                    for item in normalized_properties
                    if _has_matching_alias(item, configured_property_uuids)
                ]
                property_uuids = [
                    item["uuid"] for item in normalized_properties if item.get("uuid")
                ]
                property_uuids.extend(
                    configured_id
                    for configured_id in configured_property_uuids
                    if configured_id
                    not in {
                        alias
                        for item in normalized_properties
                        for alias in item.get("aliases", [])
                    }
                )
                normalized_properties.extend(
                    _synthetic_properties_for_missing_ids(
                        configured_property_uuids, normalized_properties
                    )
                )
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
        except HospitableApiError as err:
            raise UpdateFailed(str(err)) from err

        return {
            "properties": normalized_properties,
            "reservations": normalized_reservations,
            "diagnostics": _diagnostics(
                normalized_properties,
                normalized_reservations,
                property_uuids,
                configured_property_uuids,
            ),
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


def _has_matching_alias(property_data: dict[str, Any], values: list[str]) -> bool:
    return any(alias in values for alias in property_data.get("aliases", []))


def _synthetic_properties_for_missing_ids(
    configured_ids: list[str], properties: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing_aliases = {
        alias for property_data in properties for alias in property_data.get("aliases", [])
    }
    return [
        {
            "uuid": configured_id,
            "name": f"Hospitable {configured_id}",
            "address": None,
            "aliases": [configured_id],
            "raw": {},
        }
        for configured_id in configured_ids
        if configured_id not in existing_aliases
    ]


def _normalize_property(item: dict[str, Any]) -> dict[str, Any]:
    attrs = _attributes(item)
    aliases = _property_aliases(item, attrs)
    uuid = aliases[0] if aliases else ""
    return {
        "uuid": uuid,
        "name": attrs.get("name") or item.get("name") or uuid,
        "address": attrs.get("address") or item.get("address"),
        "aliases": aliases,
        "raw": item,
    }


def _normalize_reservation(item: dict[str, Any]) -> dict[str, Any]:
    attrs = _attributes(item)
    guest = attrs.get("guest") or item.get("guest") or item.get("guests") or {}
    property_obj = (
        attrs.get("property")
        or attrs.get("properties")
        or item.get("property")
        or item.get("properties")
        or {}
    )
    property_uuid = (
        attrs.get("property_uuid")
        or attrs.get("property_id")
        or item.get("property_uuid")
        or item.get("property_id")
        or _relationship_id(item, "property")
        or _relationship_id(item, "properties")
        or _property_object_id(property_obj)
    )
    uuid = str(item.get("id") or item.get("uuid") or attrs.get("uuid") or "")
    arrival = (
        attrs.get("arrival_date")
        or attrs.get("check_in")
        or attrs.get("checkin_date")
        or item.get("arrival_date")
        or item.get("check_in")
        or item.get("checkin_date")
    )
    departure = (
        attrs.get("departure_date")
        or attrs.get("check_out")
        or attrs.get("checkout_date")
        or item.get("departure_date")
        or item.get("check_out")
        or item.get("checkout_date")
    )
    status = (
        attrs.get("status")
        or item.get("status")
        or _reservation_status(item)
        or _reservation_status(attrs)
    )

    return {
        "uuid": uuid,
        "code": attrs.get("code") or item.get("code"),
        "status": status,
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


def _property_object_id(property_obj: Any) -> str | None:
    if isinstance(property_obj, dict):
        value = property_obj.get("uuid") or property_obj.get("id")
        return str(value) if value else None
    if isinstance(property_obj, list) and property_obj:
        first = property_obj[0]
        if isinstance(first, dict):
            value = first.get("uuid") or first.get("id")
            return str(value) if value else None
    return None


def _reservation_status(item: dict[str, Any]) -> str | None:
    reservation_status = item.get("reservation_status")
    if not isinstance(reservation_status, dict):
        return None
    current = reservation_status.get("current")
    if isinstance(current, dict):
        value = current.get("category") or current.get("status")
        return str(value) if value else None
    return str(current) if current else None


def _property_aliases(item: dict[str, Any], attrs: dict[str, Any]) -> list[str]:
    values = [
        attrs.get("uuid"),
        item.get("uuid"),
        item.get("id"),
        attrs.get("id"),
        attrs.get("property_id"),
        item.get("property_id"),
    ]
    aliases: list[str] = []
    for value in values:
        if value is None:
            continue
        alias = str(value)
        if alias and alias not in aliases:
            aliases.append(alias)
    return aliases


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
    name = guest.get("name") or guest.get("full_name") or guest.get("display_name")
    if name:
        return str(name)
    first = guest.get("first_name") or guest.get("first")
    last = guest.get("last_name") or guest.get("last")
    full_name = " ".join(str(part) for part in (first, last) if part)
    return full_name or None


def _diagnostics(
    properties: list[dict[str, Any]],
    reservations: list[dict[str, Any]],
    queried_property_uuids: list[str],
    configured_property_ids: list[str],
) -> dict[str, Any]:
    return {
        "property_count": len(properties),
        "reservation_count": len(reservations),
        "queried_property_uuids": queried_property_uuids,
        "configured_property_ids": configured_property_ids,
        "reservation_property_ids": sorted(
            {
                item["property_uuid"]
                for item in reservations
                if item.get("property_uuid")
            }
        ),
        "reservation_statuses": sorted(
            {str(item["status"]) for item in reservations if item.get("status")}
        ),
        "reservation_date_samples": [
            {
                "arrival_date": item.get("arrival_date"),
                "departure_date": item.get("departure_date"),
                "property_uuid": item.get("property_uuid"),
                "status": item.get("status"),
            }
            for item in reservations[:3]
        ],
    }
