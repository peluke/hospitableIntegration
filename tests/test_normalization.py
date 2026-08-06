"""Tests for Hospitable normalization helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, relative_path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = _load_module(
    "hospitable_api_client",
    "custom_components/hospitable_api/api.py",
)
normalization = _load_module(
    "hospitable_normalization",
    "custom_components/hospitable_api/normalization.py",
)


def test_normalize_property_json_api_shape():
    item = {
        "id": "numeric-1",
        "attributes": {"uuid": "property-1", "name": "Cabin"},
    }

    assert normalization.normalize_property(item)["uuid"] == "property-1"
    assert normalization.normalize_property(item)["name"] == "Cabin"
    assert normalization.normalize_property(item)["aliases"] == [
        "property-1",
        "numeric-1",
    ]


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

    normalized = normalization.normalize_reservation(item)

    assert normalized["uuid"] == "reservation-1"
    assert normalized["property_uuid"] == "property-1"
    assert normalized["guest_name"] == "Ada Lovelace"


def test_reservation_query_uses_hospitable_property_array_params():
    params = api._reservation_query_params(
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

    assert normalization.dedupe_reservations(reservations) == [
        {"uuid": "reservation-1", "date_query": "checkin"},
        {"uuid": "reservation-2", "date_query": "checkout"},
    ]


def test_matching_property_aliases():
    property_data = {"uuid": "property-uuid", "aliases": ["property-uuid", "12345"]}

    assert normalization.has_matching_alias(property_data, ["12345"])
    assert not normalization.has_matching_alias(property_data, ["67890"])


def test_synthetic_properties_for_missing_configured_ids():
    properties = [{"uuid": "property-1", "aliases": ["property-1", "12345"]}]

    assert normalization.synthetic_properties_for_missing_ids(
        ["12345", "property-2"], properties
    ) == [
        {
            "uuid": "property-2",
            "name": "Hospitable property-2",
            "address": None,
            "aliases": ["property-2"],
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

    normalized = normalization.normalize_reservation(item)

    assert normalized["arrival_date"] == "2026-08-06T16:00:00Z"
    assert normalized["departure_date"] == "2026-08-08T11:00:00Z"
    assert normalized["status"] == "accepted"
    assert normalized["guest_name"] == "Grace Hopper"
    assert normalized["property_uuid"] == "property-1"


def test_normalize_reservation_uses_first_list_items():
    item = {
        "id": "reservation-1",
        "guests": [{"first_name": "Grace", "last_name": "Hopper"}],
        "properties": [{"id": "property-1", "name": "Cabin"}],
    }

    normalized = normalization.normalize_reservation(item)

    assert normalized["guest_name"] == "Grace Hopper"
    assert normalized["property_uuid"] == "property-1"
    assert normalized["property_name"] == "Cabin"


def test_normalize_reservation_ignores_malformed_list_items():
    item = {
        "id": "reservation-1",
        "guests": ["unexpected"],
        "properties": ["unexpected"],
    }

    normalized = normalization.normalize_reservation(item)

    assert normalized["guest_name"] is None
    assert normalized["property_uuid"] is None
    assert normalized["property_name"] is None


def test_dedupe_strings_strips_and_preserves_order():
    assert normalization.dedupe_strings(
        [" property-1 ", "property-2", "property-1", ""]
    ) == ["property-1", "property-2"]


def test_reservations_by_property_matches_aliases():
    properties = [{"uuid": "property-1", "aliases": ["property-1", "12345"]}]
    reservations = [
        {"uuid": "reservation-1", "property_uuid": "12345"},
        {"uuid": "reservation-2", "property_uuid": "other"},
    ]

    assert normalization.reservations_by_property(properties, reservations) == {
        "property-1": [{"uuid": "reservation-1", "property_uuid": "12345"}]
    }


def test_has_next_page_uses_common_pagination_shapes():
    assert api._has_next_page({"meta": {"last_page": 2}}, 1, 100)
    assert api._has_next_page(
        {"links": {"next": "https://example.test/next"}}, 1, 100
    )
    assert not api._has_next_page({"meta": {"last_page": 2}}, 2, 100)
    assert not api._has_next_page({}, 1, 0)


def test_extract_collection_ignores_non_dict_items():
    payload = {"data": [{"id": "one"}, "unexpected", {"id": "two"}]}

    assert api._extract_collection(payload) == [{"id": "one"}, {"id": "two"}]


def test_task_query_uses_hospitable_property_array_params():
    params = api._task_query_params(
        start_date="2026-08-06",
        end_date="2026-09-06",
        property_uuids=["property-1", "property-2"],
    )

    assert ("properties[]", "property-1") in params
    assert ("properties[]", "property-2") in params
    assert ("per_page", "100") in params
    assert not any(key == "include" for key, _value in params)


def test_normalize_task_common_shape():
    item = {
        "id": "task-1",
        "title": "Cleaning",
        "status": "open",
        "acceptance_status": "pending",
        "due_date": "2026-08-13T11:00:00Z",
        "properties": [{"id": "property-1", "name": "Manzanita"}],
        "reservation": {"id": "reservation-1"},
        "teammate": {"id": "teammate-1", "name": "Charlotte"},
    }

    normalized = normalization.normalize_task(item)

    assert normalized["uuid"] == "task-1"
    assert normalized["title"] == "Cleaning"
    assert normalized["assignment_status"] == "pending"
    assert normalized["property_uuid"] == "property-1"
    assert normalized["reservation_uuid"] == "reservation-1"
    assert normalized["assignee_name"] == "Charlotte"


def test_response_key_sample_exposes_structure_only():
    item = {
        "id": "task-1",
        "attributes": {
            "private_note": "do not expose",
            "status": "pending",
        },
    }

    assert normalization.response_key_sample(item) == {
        "keys": ["attributes", "id"],
        "attribute_keys": ["private_note", "status"],
    }


def test_checkout_tasks_by_property_matches_checkout_dates():
    properties = [{"uuid": "property-1", "aliases": ["property-1", "12345"]}]
    reservations = [
        {
            "uuid": "reservation-1",
            "property_uuid": "12345",
            "departure_date": "2026-08-13T11:00:00Z",
        }
    ]
    tasks = [
        {
            "uuid": "task-1",
            "property_uuid": "property-1",
            "due_date": "2026-08-13T10:00:00Z",
        },
        {
            "uuid": "task-2",
            "property_uuid": "property-1",
            "due_date": "2026-08-14T10:00:00Z",
        },
    ]

    assert normalization.checkout_tasks_by_property(
        properties,
        reservations,
        tasks,
    ) == {"property-1": [tasks[0]]}


def test_checkout_tasks_by_property_returns_empty_list_without_matches():
    properties = [{"uuid": "property-1", "aliases": ["property-1"]}]

    assert normalization.checkout_tasks_by_property(properties, [], []) == {
        "property-1": []
    }
