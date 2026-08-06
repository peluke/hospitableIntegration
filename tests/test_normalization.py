"""Tests for Hospitable normalization helpers."""

from custom_components.hospitable_api.api import _reservation_query_params
from custom_components.hospitable_api.coordinator import (
    _dedupe_reservations,
    _normalize_property,
    _normalize_reservation,
)


def test_normalize_property_json_api_shape():
    item = {"id": "property-1", "attributes": {"name": "Cabin"}}

    assert _normalize_property(item)["uuid"] == "property-1"
    assert _normalize_property(item)["name"] == "Cabin"


def test_normalize_reservation_json_api_shape():
    item = {
        "id": "reservation-1",
        "attributes": {
            "code": "ABC123",
            "arrival_date": "2026-08-06",
            "departure_date": "2026-08-08",
            "guest": {"first_name": "Ada", "last_name": "Lovelace"},
        },
        "relationships": {"properties": {"data": {"id": "property-1"}}},
    }

    normalized = _normalize_reservation(item)

    assert normalized["uuid"] == "reservation-1"
    assert normalized["property_uuid"] == "property-1"
    assert normalized["guest_name"] == "Ada Lovelace"


def test_reservation_query_uses_hospitable_property_array_params():
    params = _reservation_query_params(
        start_date="2026-08-06",
        end_date="2026-09-06",
        date_query="checkin",
        property_uuids=["property-1", "property-2"],
    )

    assert ("properties[]", "property-1") in params
    assert ("properties[]", "property-2") in params
    assert ("properties", "property-1,property-2") not in params


def test_dedupe_reservations_by_uuid():
    reservations = [
        {"uuid": "reservation-1", "date_query": "checkin"},
        {"uuid": "reservation-1", "date_query": "checkout"},
        {"uuid": "reservation-2", "date_query": "checkout"},
    ]

    assert _dedupe_reservations(reservations) == [
        {"uuid": "reservation-1", "date_query": "checkin"},
        {"uuid": "reservation-2", "date_query": "checkout"},
    ]
