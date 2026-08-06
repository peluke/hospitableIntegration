"""Pure normalization helpers for Hospitable Integration responses."""

from __future__ import annotations

from typing import Any

MAX_RESPONSE_KEY_SAMPLE_SIZE = 30


def dedupe_strings(values: Any) -> list[str]:
    """Strip, dedupe, and preserve order for string-like values."""
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def dedupe_reservations(reservations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe reservations by UUID while preserving API order."""
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


def has_matching_alias(property_data: dict[str, Any], values: list[str]) -> bool:
    """Return whether a normalized property has any configured alias."""
    return any(alias in values for alias in property_data.get("aliases", []))


def aliases_for_properties(properties: list[dict[str, Any]]) -> set[str]:
    """Return all non-empty aliases from normalized properties."""
    return {
        alias
        for property_data in properties
        for alias in property_data.get("aliases", [])
        if alias
    }


def synthetic_properties_for_missing_ids(
    configured_ids: list[str], properties: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return placeholder properties for configured IDs missing from /properties."""
    existing_aliases = aliases_for_properties(properties)
    return [
        {
            "uuid": configured_id,
            "name": f"Hospitable {configured_id}",
            "address": None,
            "aliases": [configured_id],
        }
        for configured_id in configured_ids
        if configured_id not in existing_aliases
    ]


def normalize_property(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Hospitable property across known response shapes."""
    attrs = _attributes(item)
    aliases = _property_aliases(item, attrs)
    uuid = aliases[0] if aliases else ""
    return {
        "uuid": uuid,
        "name": attrs.get("name") or item.get("name") or uuid,
        "address": attrs.get("address") or item.get("address"),
        "aliases": aliases,
    }


def normalize_reservation(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Hospitable reservation across known response shapes."""
    attrs = _attributes(item)
    guest = _first_dict(attrs.get("guest") or item.get("guest") or item.get("guests"))
    property_obj = _first_dict(
        attrs.get("property")
        or attrs.get("properties")
        or item.get("property")
        or item.get("properties")
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
        "property_uuid": str(property_uuid) if property_uuid else None,
        "property_name": property_obj.get("name"),
    }


def normalize_task(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Hospitable task across known response shapes."""
    attrs = _attributes(item)
    property_obj = _first_dict(
        attrs.get("property")
        or attrs.get("properties")
        or item.get("property")
        or item.get("properties")
    )
    reservation_obj = _first_dict(
        attrs.get("reservation")
        or attrs.get("reservations")
        or item.get("reservation")
        or item.get("reservations")
    )
    assignee = _first_dict(
        attrs.get("assignee")
        or attrs.get("teammate")
        or attrs.get("assigned_to")
        or item.get("assignee")
        or item.get("teammate")
        or item.get("assigned_to")
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
    reservation_uuid = (
        attrs.get("reservation_uuid")
        or attrs.get("reservation_id")
        or item.get("reservation_uuid")
        or item.get("reservation_id")
        or _relationship_id(item, "reservation")
        or _relationship_id(item, "reservations")
        or reservation_obj.get("uuid")
        or reservation_obj.get("id")
    )
    due_date = (
        attrs.get("due_date")
        or attrs.get("scheduled_date")
        or attrs.get("start_date")
        or attrs.get("starts_at")
        or attrs.get("date")
        or item.get("due_date")
        or item.get("scheduled_date")
        or item.get("start_date")
        or item.get("starts_at")
        or item.get("date")
    )
    status = (
        attrs.get("status")
        or attrs.get("state")
        or item.get("status")
        or item.get("state")
    )
    assignment_status = (
        attrs.get("assignment_status")
        or attrs.get("acceptance_status")
        or attrs.get("assignee_status")
        or attrs.get("teammate_status")
        or item.get("assignment_status")
        or item.get("acceptance_status")
        or item.get("assignee_status")
        or item.get("teammate_status")
        or assignee.get("assignment_status")
        or assignee.get("acceptance_status")
        or assignee.get("status")
    )

    return {
        "uuid": str(item.get("id") or item.get("uuid") or attrs.get("uuid") or ""),
        "title": (
            attrs.get("title")
            or attrs.get("name")
            or attrs.get("summary")
            or item.get("title")
            or item.get("name")
            or item.get("summary")
            or "Task"
        ),
        "status": str(status) if status else None,
        "assignment_status": str(assignment_status) if assignment_status else None,
        "due_date": due_date,
        "property_uuid": str(property_uuid) if property_uuid else None,
        "property_name": property_obj.get("name"),
        "reservation_uuid": str(reservation_uuid) if reservation_uuid else None,
        "assignee_name": _guest_name(assignee),
        "assignee_uuid": _object_identifier(assignee),
    }


def response_key_sample(item: dict[str, Any]) -> dict[str, list[str]]:
    """Return structural response keys without exposing response values."""
    attrs = _attributes(item)
    return {
        "keys": sorted(str(key) for key in item)[:MAX_RESPONSE_KEY_SAMPLE_SIZE],
        "attribute_keys": sorted(str(key) for key in attrs)[:MAX_RESPONSE_KEY_SAMPLE_SIZE],
    }


def checkout_tasks_by_property(
    properties: list[dict[str, Any]],
    reservations: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group tasks that land on a checkout date by canonical property UUID."""
    indexed: dict[str, list[dict[str, Any]]] = {
        property_data["uuid"]: []
        for property_data in properties
        if property_data.get("uuid")
    }
    aliases_by_property = _aliases_by_property(properties)
    checkout_dates_by_property = _checkout_dates_by_property(
        properties,
        reservations,
        aliases_by_property,
    )

    for task in tasks:
        task_date = _date_text(task.get("due_date"))
        task_property_uuid = task.get("property_uuid")
        if not task_date or not task_property_uuid:
            continue
        for canonical_uuid, aliases in aliases_by_property.items():
            if task_property_uuid not in aliases:
                continue
            if task_date in checkout_dates_by_property.get(canonical_uuid, set()):
                indexed.setdefault(canonical_uuid, []).append(task)
            break

    return indexed


def reservations_by_property(
    properties: list[dict[str, Any]], reservations: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Index normalized reservations by canonical property UUID."""
    indexed: dict[str, list[dict[str, Any]]] = {
        property_data["uuid"]: []
        for property_data in properties
        if property_data.get("uuid")
    }
    canonical_by_alias: dict[str, str] = {}
    for property_data in properties:
        canonical_uuid = property_data.get("uuid")
        if not canonical_uuid:
            continue
        for alias in property_data.get("aliases", []):
            canonical_by_alias[alias] = canonical_uuid

    for reservation in reservations:
        property_uuid = reservation.get("property_uuid")
        if not property_uuid:
            continue
        canonical_uuid = canonical_by_alias.get(property_uuid)
        if canonical_uuid:
            indexed.setdefault(canonical_uuid, []).append(reservation)
    return indexed


def _aliases_by_property(properties: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {
        property_data["uuid"]: set(property_data.get("aliases", []))
        for property_data in properties
        if property_data.get("uuid")
    }


def _checkout_dates_by_property(
    properties: list[dict[str, Any]],
    reservations: list[dict[str, Any]],
    aliases_by_property: dict[str, set[str]],
) -> dict[str, set[str]]:
    checkout_dates: dict[str, set[str]] = {
        property_data["uuid"]: set()
        for property_data in properties
        if property_data.get("uuid")
    }
    for reservation in reservations:
        property_uuid = reservation.get("property_uuid")
        departure_date = _date_text(reservation.get("departure_date"))
        if not property_uuid or not departure_date:
            continue
        for canonical_uuid, aliases in aliases_by_property.items():
            if property_uuid in aliases:
                checkout_dates.setdefault(canonical_uuid, set()).add(departure_date)
                break
    return checkout_dates


def _date_text(value: Any) -> str | None:
    if not value:
        return None
    return str(value)[:10]


def _attributes(item: dict[str, Any]) -> dict[str, Any]:
    attrs = item.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


def _first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


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


def _object_identifier(value: dict[str, Any]) -> str | None:
    identifier = value.get("uuid") or value.get("id")
    return str(identifier) if identifier else None
