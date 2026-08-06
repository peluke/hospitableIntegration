"""Async client for Hospitable Public API v2."""

from __future__ import annotations

from collections.abc import Mapping
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
        property_uuids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return reservations for a date range."""
        params: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
            "include": "guest,properties,listings",
        }
        if property_uuids:
            params["properties"] = ",".join(property_uuids)

        payload = await self._request("GET", "/reservations", params=params)
        return _extract_collection(payload)

    async def async_post_guest_message(self, reservation_uuid: str, message: str) -> None:
        """Post a message to the guest conversation for a reservation."""
        await self._request(
            "POST",
            f"/reservations/{reservation_uuid}/messages",
            json={"message": message},
        )

    async def async_validate_token(self) -> None:
        """Validate API credentials using a lightweight endpoint."""
        await self._request("GET", "/properties")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
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
                response.raise_for_status()
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

