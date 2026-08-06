"""Tests for Hospitable normalization helpers."""

from custom_components.hospitable_api.coordinator import _normalize_property, _normalize_reservation


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

