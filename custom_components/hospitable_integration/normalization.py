"""Pure normalization helpers for Hospitable Integration responses."""

from __future__ import annotations

from typing import Any


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
