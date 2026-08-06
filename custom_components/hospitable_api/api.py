"""Async client for Hospitable Public API v2."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

API_BASE_URL = "https://public.api.hospitable.com/v2"


class HospitableApiError(Exception):
    """Raised when the Hospitable API request fails."""


class HospitableApiClient:
    """Small Hospitable API client."""

    def __init__(self, session: ClientSession, api_token: str) -> None:
        self._session = session
        self._api_token = api_token

    async def async_get_properties(self) -> list[dict[str, Any]]:
        """Return Hospitable properties."""
        payload = await self._request("GET", "/properties")
        return _extract_collection(payload)

    async def async_get_reservations(
        self,
        *,
        start_date: str,
        end_date: str,
        date_query: str,
        property_uuids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return reservations for a date range."""
        params = _reservation_query_params(
            start_date=start_date,
            end_date=end_date,
            date_query=date_query,
            property_uuids=property_uuids or [],
        )
        payload = await self._request("GET", "/reservations", params=params)
        return _extract_collection(payload)

    async def async_post_guest_message(self, reservation_uuid: str, message: str) -> None:
        """Post a message to the guest conversation for a reservation."""
        await self._request(
            "POST",
            f"/reservations/{reservation_uuid}/messages",
            json={"body": message},
        )

    async def async_validate_token(self) -> None:
        """Validate API credentials using a lightweight endpoint."""
        await self._request("GET", "/properties")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: list[tuple[str, str]] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_token}",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=headers,
                params=params,
                json=json,
                timeout=30,
            ) as response:
                if response.status >= 400:
                    message = await _response_error_message(response)
                    raise HospitableApiError(f"{response.status} {message}")
                if response.status == 204:
                    return {}
                return await response.json()
        except ClientResponseError as err:
            raise HospitableApiError(f"{err.status} {err.message}") from err
        except ClientError as err:
            raise HospitableApiError(str(err)) from err


def _extract_collection(payload: Any) -> list[dict[str, Any]]:
    """Extract a list from common JSON API and plain-list response shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]

    items = payload.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]

    return []


def _reservation_query_params(
    *,
    start_date: str,
    end_date: str,
    date_query: str,
    property_uuids: list[str],
) -> list[tuple[str, str]]:
    params = [
        ("date_query", date_query),
        ("start_date", start_date),
        ("end_date", end_date),
        ("per_page", "100"),
        ("include", "guest,properties,listings"),
    ]
    params.extend(("properties[]", uuid) for uuid in property_uuids)
    return params


async def _response_error_message(response: Any) -> str:
    """Return the most useful API error message available."""
    try:
        payload = await response.json()
    except (ClientError, ValueError):
        payload = None

    if isinstance(payload, dict):
        for key in ("message", "error", "detail", "title"):
            value = payload.get(key)
            if value:
                return str(value)
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            return str(errors[0])
        return str(payload)

    text = await response.text()
    return text or response.reason
