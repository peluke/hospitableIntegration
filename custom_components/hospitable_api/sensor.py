"""Sensors for Hospitable API."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HospitableDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hospitable API sensors."""
    coordinator: HospitableDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for property_data in coordinator.data.get("properties", []):
        entities.extend(
            [
                HospitableGuestSensor(coordinator, property_data, "current"),
                HospitableGuestSensor(coordinator, property_data, "next"),
                HospitableGuestSensor(coordinator, property_data, "upcoming"),
            ]
        )

    async_add_entities(entities)


class HospitableGuestSensor(
    CoordinatorEntity[HospitableDataUpdateCoordinator], SensorEntity
):
    """Sensor exposing Hospitable guest reservation data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HospitableDataUpdateCoordinator,
        property_data: dict[str, Any],
        sensor_kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._property_uuid = property_data["uuid"]
        self._property_name = property_data["name"]
        self._property_aliases = property_data.get("aliases", [self._property_uuid])
        self._sensor_kind = sensor_kind
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._property_uuid)},
            "name": self._property_name,
            "manufacturer": "Hospitable",
        }
        self._attr_unique_id = f"{DOMAIN}_{self._property_uuid}_{sensor_kind}"
        self._attr_name = {
            "current": "Current Guest",
            "next": "Next Guest",
            "upcoming": "Upcoming Guests",
        }[sensor_kind]

    @property
    def native_value(self) -> str | int | None:
        """Return the sensor state."""
        if self._sensor_kind == "upcoming":
            return len(self._upcoming_reservations())

        reservation = self._selected_reservation()
        if reservation is None:
            return "None"
        return (
            reservation.get("guest_name")
            or reservation.get("code")
            or reservation.get("uuid")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return reservation details as attributes."""
        if self._sensor_kind == "upcoming":
            return {
                "property_uuid": self._property_uuid,
                "property_name": self._property_name,
                "reservations": [
                    _public_reservation_attrs(item)
                    for item in self._upcoming_reservations()
                ],
            }

        reservation = self._selected_reservation()
        attrs: dict[str, Any] = {
            "property_uuid": self._property_uuid,
            "property_name": self._property_name,
        }
        if reservation:
            attrs.update(_public_reservation_attrs(reservation))
        return attrs

    def _selected_reservation(self) -> dict[str, Any] | None:
        reservations = self._reservations_for_property()
        today = dt_util.now().date()
        if self._sensor_kind == "current":
            for reservation in reservations:
                arrival = _parse_date(reservation.get("arrival_date"))
                departure = _parse_date(reservation.get("departure_date"))
                if arrival and departure and arrival <= today < departure:
                    return reservation
            return None

        upcoming = self._upcoming_reservations()
        return upcoming[0] if upcoming else None

    def _upcoming_reservations(self) -> list[dict[str, Any]]:
        today = dt_util.now().date()
        upcoming = []
        for reservation in self._reservations_for_property():
            arrival = _parse_date(reservation.get("arrival_date"))
            if arrival and arrival >= today:
                upcoming.append(reservation)
        return sorted(upcoming, key=lambda item: item.get("arrival_date") or "")

    def _reservations_for_property(self) -> list[dict[str, Any]]:
        reservations: list[dict[str, Any]] = self.coordinator.data.get("reservations", [])
        return [
            item
            for item in reservations
            if item.get("property_uuid") in self._property_aliases
            and item.get("status") != "cancelled"
        ]


def _public_reservation_attrs(reservation: dict[str, Any]) -> dict[str, Any]:
    return {
        "reservation_uuid": reservation.get("uuid"),
        "reservation_code": reservation.get("code"),
        "guest_name": reservation.get("guest_name"),
        "arrival_date": reservation.get("arrival_date"),
        "departure_date": reservation.get("departure_date"),
        "status": reservation.get("status"),
        "platform": reservation.get("platform"),
    }


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
