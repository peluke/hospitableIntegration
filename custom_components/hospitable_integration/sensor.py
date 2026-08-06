"""Sensors for Hospitable Integration."""

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

RESERVATION_FIELD_SENSORS: dict[str, tuple[str, str]] = {
    "uuid": ("Reservation UUID", "uuid"),
    "code": ("Reservation Code", "code"),
    "arrival_date": ("Check In", "arrival_date"),
    "departure_date": ("Check Out", "departure_date"),
    "status": ("Status", "status"),
    "platform": ("Platform", "platform"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hospitable Integration sensors."""
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
        for sensor_kind in ("current", "next"):
            entities.extend(
                HospitableGuestSensor(
                    coordinator,
                    property_data,
                    sensor_kind,
                    reservation_field=reservation_field,
                )
                for reservation_field in RESERVATION_FIELD_SENSORS
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
        reservation_field: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._property_uuid = property_data["uuid"]
        self._property_name = property_data["name"]
        self._property_aliases = property_data.get("aliases", [self._property_uuid])
        self._sensor_kind = sensor_kind
        self._reservation_field = reservation_field
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._property_uuid)},
            "name": self._property_name,
            "manufacturer": "Hospitable",
        }
        self._attr_unique_id = self._unique_id()
        self._attr_name = self._entity_name()

    @property
    def native_value(self) -> str | int | None:
        """Return the sensor state."""
        if self._sensor_kind == "upcoming":
            return len(self._upcoming_reservations())

        reservation = self._selected_reservation()
        if reservation is None:
            return "None"
        if self._reservation_field:
            return _field_value(reservation, self._reservation_field)
        return (
            reservation.get("guest_name")
            or reservation.get("code")
            or reservation.get("uuid")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return reservation details as attributes."""
        include_diagnostics = self._reservation_field is None
        if self._sensor_kind == "upcoming":
            attrs: dict[str, Any] = {
                "property_uuid": self._property_uuid,
                "property_name": self._property_name,
                "property_aliases": self._property_aliases,
                "reservations": [
                    _public_reservation_attrs(item)
                    for item in self._upcoming_reservations()
                ],
            }
            if include_diagnostics:
                attrs.update(self._diagnostic_attrs())
            return attrs

        reservation = self._selected_reservation()
        attrs: dict[str, Any] = {
            "property_uuid": self._property_uuid,
            "property_name": self._property_name,
            "property_aliases": self._property_aliases,
        }
        if include_diagnostics:
            attrs.update(self._diagnostic_attrs())
        if reservation:
            attrs.update(_public_reservation_attrs(reservation))
        return attrs

    def _unique_id(self) -> str:
        if self._reservation_field:
            return (
                f"{DOMAIN}_{self._property_uuid}_{self._sensor_kind}_"
                f"{self._reservation_field}"
            )
        return f"{DOMAIN}_{self._property_uuid}_{self._sensor_kind}"

    def _entity_name(self) -> str:
        if self._reservation_field:
            prefix = "Current" if self._sensor_kind == "current" else "Next"
            field_name = RESERVATION_FIELD_SENSORS[self._reservation_field][0]
            return f"{prefix} {field_name}"
        return {
            "current": "Current Guest",
            "next": "Next Guest",
            "upcoming": "Upcoming Guests",
        }[self._sensor_kind]

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
        reservations_by_property: dict[str, list[dict[str, Any]]] = (
            self.coordinator.data.get("reservations_by_property", {})
        )
        return [
            item
            for item in reservations_by_property.get(self._property_uuid, [])
            if not _is_cancelled(item.get("status"))
        ]

    def _diagnostic_attrs(self) -> dict[str, Any]:
        diagnostics = self.coordinator.data.get("diagnostics", {})
        reservations: list[dict[str, Any]] = self.coordinator.data.get("reservations", [])
        return {
            "hospitable_property_count": diagnostics.get("property_count"),
            "hospitable_reservation_count": diagnostics.get("reservation_count"),
            "hospitable_queried_property_uuids": diagnostics.get("queried_property_uuids"),
            "hospitable_reservation_property_ids": diagnostics.get("reservation_property_ids"),
            "hospitable_reservation_statuses": diagnostics.get("reservation_statuses"),
            "hospitable_matched_reservation_count": len(self._reservations_for_property()),
            "hospitable_unmatched_reservation_samples": [
                _public_reservation_attrs(item)
                for item in reservations
                if item.get("property_uuid") not in self._property_aliases
            ][:3],
            "hospitable_reservation_date_samples": diagnostics.get(
                "reservation_date_samples"
            ),
        }


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


def _field_value(reservation: dict[str, Any], field: str) -> str:
    value = reservation.get(RESERVATION_FIELD_SENSORS[field][1])
    return str(value) if value else "None"


def _is_cancelled(status: Any) -> bool:
    return str(status or "").lower() in {"cancelled", "canceled", "not accepted"}


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
