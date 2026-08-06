"""Data update coordinator for Hospitable API."""

from __future__ import annotations

import logging
from datetime import timedelta
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
from .normalization import (
    aliases_for_properties,
    dedupe_reservations,
    dedupe_strings,
    has_matching_alias,
    normalize_property,
    normalize_reservation,
    reservations_by_property,
    synthetic_properties_for_missing_ids,
)

_LOGGER = logging.getLogger(__name__)
DATE_QUERY_CHECKIN = "checkin"
DATE_QUERY_CHECKOUT = "checkout"


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
            normalized_properties = [normalize_property(item) for item in properties]
            if configured_property_uuids:
                normalized_properties = [
                    item
                    for item in normalized_properties
                    if has_matching_alias(item, configured_property_uuids)
                ]
                existing_aliases = aliases_for_properties(normalized_properties)
                property_uuids = dedupe_strings(
                    item["uuid"] for item in normalized_properties if item.get("uuid")
                )
                property_uuids.extend(
                    configured_id
                    for configured_id in configured_property_uuids
                    if configured_id not in existing_aliases
                )
                normalized_properties.extend(
                    synthetic_properties_for_missing_ids(
                        configured_property_uuids, normalized_properties
                    )
                )
            else:
                property_uuids = dedupe_strings(
                    item["uuid"] for item in normalized_properties if item.get("uuid")
                )
            if not property_uuids:
                raise UpdateFailed(
                    "No Hospitable property UUIDs found. Enter at least one property UUID in the integration configuration."
                )
            reservations = await self.api.async_get_reservations(
                start_date=today.isoformat(),
                end_date=end_date.isoformat(),
                date_query=DATE_QUERY_CHECKIN,
                property_uuids=property_uuids,
            )
            reservations.extend(
                await self.api.async_get_reservations(
                    start_date=today.isoformat(),
                    end_date=end_date.isoformat(),
                    date_query=DATE_QUERY_CHECKOUT,
                    property_uuids=property_uuids,
                )
            )
            normalized_reservations = dedupe_reservations(
                [normalize_reservation(item) for item in reservations]
            )
        except HospitableApiError as err:
            raise UpdateFailed(str(err)) from err

        return {
            "properties": normalized_properties,
            "reservations": normalized_reservations,
            "reservations_by_property": reservations_by_property(
                normalized_properties, normalized_reservations
            ),
            "diagnostics": _diagnostics(
                normalized_properties,
                normalized_reservations,
                property_uuids,
                configured_property_uuids,
            ),
        }


def _parse_property_uuids(raw_value: str) -> list[str]:
    return dedupe_strings(raw_value.split(","))


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
