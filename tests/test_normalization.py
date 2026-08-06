"""Tests for Hospitable normalization helpers."""

from custom_components.hospitable_api.api import _reservation_query_params
from custom_components.hospitable_api.coordinator import (
    _dedupe_reservations,
    _has_matching_alias,
    _normalize_property,
    _normalize_reservation,
    _synthetic_properties_for_missing_ids,
)


def test_normalize_property_json_api_shape():
    item = {
        "id": "numeric-1",
        "attributes": {"uuid": "property-1", "name": "Cabin"},
    }

    assert _normalize_property(item)["uuid"] == "property-1"
    assert _normalize_property(item)["name"] == "Cabin"
    assert _normalize_property(item)["aliases"] == ["property-1", "numeric-1"]


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
    assert ("per_page", "100") in params
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


def test_matching_property_aliases():
    property_data = {"uuid": "property-uuid", "aliases": ["property-uuid", "12345"]}

    assert _has_matching_alias(property_data, ["12345"])
    assert not _has_matching_alias(property_data, ["67890"])


def test_synthetic_properties_for_missing_configured_ids():
    properties = [{"uuid": "property-1", "aliases": ["property-1", "12345"]}]

    assert _synthetic_properties_for_missing_ids(
        ["12345", "property-2"], properties
    ) == [
        {
            "uuid": "property-2",
            "name": "Hospitable property-2",
            "address": None,
            "aliases": ["property-2"],
            "raw": {},
        }
    ]


def test_normalize_reservation_hospitable_public_api_shape():
    item = {
        "id": "reservation-1",
        "platform": "airbnb",
        "check_in": "2026-08-06T16:00:00Z",
        "check_out": "2026-08-08T11:00:00Z",
        "reservation_status": {"current": {"category": "accepted"}},
        "guests": {"first_name": "Grace", "last_name": "Hopper"},
        "properties": [{"id": "property-1", "name": "Cabin"}],
    }

    normalized = _normalize_reservation(item)

    assert normalized["arrival_date"] == "2026-08-06T16:00:00Z"
    assert normalized["departure_date"] == "2026-08-08T11:00:00Z"
    assert normalized["status"] == "accepted"
    assert normalized["guest_name"] == "Grace Hopper"
    assert normalized["property_uuid"] == "property-1"
