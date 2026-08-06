#!/usr/bin/env python3
"""Probe Hospitable task responses without storing credentials.

Set HOSPITABLE_API_TOKEN before running. Property IDs can be passed with
--property or HOSPITABLE_PROPERTY_UUIDS.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE_URL = "https://public.api.hospitable.com/v2"
DEFAULT_LOOKAHEAD_DAYS = 60
DEFAULT_PAGE_SIZE = 100
STATUS_KEY_FRAGMENTS = (
    "accept",
    "assign",
    "declin",
    "state",
    "status",
    "team",
)


class ProbeError(Exception):
    """Raised when the diagnostic probe cannot complete."""


def main() -> int:
    args = _parse_args()
    token = os.environ.get("HOSPITABLE_API_TOKEN")
    if not token:
        print("Set HOSPITABLE_API_TOKEN before running.", file=sys.stderr)
        return 2

    property_uuids = _property_uuids(args)
    try:
        if args.task_id:
            task = _request(token, f"/tasks/{args.task_id}")
            _print_task_detail(args.task_id, task, show_values=args.show_values)
            return 0

        tasks = _request_collection(
            token,
            "/tasks",
            _task_params(args.start_date, args.end_date, property_uuids),
            max_pages=args.max_pages,
        )
        print(f"Task count: {len(tasks)}")
        print(f"Date range: {args.start_date} to {args.end_date}")
        if property_uuids:
            print(f"Property UUIDs: {', '.join(property_uuids)}")
        print()

        for task in tasks[: args.limit]:
            _print_task_summary(
                token,
                task,
                fetch_detail=args.fetch_detail,
                show_values=args.show_values,
            )
    except ProbeError as err:
        print(f"Probe failed: {err}", file=sys.stderr)
        return 1
    return 0


def _parse_args() -> argparse.Namespace:
    today = datetime.now().astimezone().date()
    parser = argparse.ArgumentParser(
        description="Inspect Hospitable task list/detail response structure."
    )
    parser.add_argument(
        "--start-date",
        default=today.isoformat(),
        help="Start date for /tasks query, default: today.",
    )
    parser.add_argument(
        "--end-date",
        default=(today + timedelta(days=DEFAULT_LOOKAHEAD_DAYS)).isoformat(),
        help=f"End date for /tasks query, default: today + {DEFAULT_LOOKAHEAD_DAYS}.",
    )
    parser.add_argument(
        "--property",
        action="append",
        default=[],
        help="Hospitable property UUID. Can be passed more than once.",
    )
    parser.add_argument(
        "--task-id",
        help="Fetch one task detail directly instead of listing tasks.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of list tasks to print. Default: 10.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Maximum list pages to fetch. Default: 3.",
    )
    parser.add_argument(
        "--fetch-detail",
        action="store_true",
        help="Also call /tasks/{id} for each printed list task.",
    )
    parser.add_argument(
        "--show-values",
        action="store_true",
        help="Print candidate status/assignment values. Use only locally.",
    )
    return parser.parse_args()


def _property_uuids(args: argparse.Namespace) -> list[str]:
    values = list(args.property)
    env_value = os.environ.get("HOSPITABLE_PROPERTY_UUIDS", "")
    values.extend(env_value.split(","))
    return _dedupe(value.strip() for value in values if value.strip())


def _task_params(
    start_date: str, end_date: str, property_uuids: list[str]
) -> list[tuple[str, str]]:
    params = [
        ("start_date", start_date),
        ("end_date", end_date),
        ("per_page", str(DEFAULT_PAGE_SIZE)),
    ]
    params.extend(("properties[]", uuid) for uuid in property_uuids)
    return params


def _request_collection(
    token: str,
    path: str,
    params: list[tuple[str, str]],
    *,
    max_pages: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        payload = _request(token, path, [*params, ("page", str(page))])
        page_items = _extract_collection(payload)
        items.extend(page_items)
        if not _has_next_page(payload, page, len(page_items)):
            break
    return items


def _request(
    token: str,
    path: str,
    params: list[tuple[str, str]] | None = None,
) -> Any:
    query = f"?{urlencode(params or [])}" if params else ""
    request = Request(
        f"{API_BASE_URL}{path}{query}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        raise ProbeError(f"{err.code} {body}") from err
    except URLError as err:
        raise ProbeError(str(err.reason)) from err
    except json.JSONDecodeError as err:
        raise ProbeError("Invalid JSON response") from err


def _print_task_summary(
    token: str,
    task: dict[str, Any],
    *,
    fetch_detail: bool,
    show_values: bool,
) -> None:
    task_id = str(task.get("id") or task.get("uuid") or "")
    print(f"Task: {task_id or '(missing id)'}")
    _print_structure(task, show_values=show_values)
    if fetch_detail and task_id:
        try:
            detail = _request(token, f"/tasks/{task_id}")
        except ProbeError as err:
            print(f"  Detail error: {err}")
        else:
            print("  Detail:")
            _print_structure(detail, indent="    ", show_values=show_values)
    print()


def _print_task_detail(
    task_id: str,
    task: dict[str, Any],
    *,
    show_values: bool,
) -> None:
    print(f"Task detail: {task_id}")
    _print_structure(task, show_values=show_values)
    print()
    print("Candidate status/assignment paths:")
    matches = _candidate_paths(task)
    if not matches:
        print("  (none found)")
        return
    for path, value in matches:
        if show_values:
            print(f"  {path}: {json.dumps(value, default=str)}")
        else:
            print(f"  {path}")


def _print_structure(
    payload: dict[str, Any],
    *,
    indent: str = "  ",
    show_values: bool = False,
) -> None:
    attrs = payload.get("attributes") if isinstance(payload, dict) else None
    relationships = payload.get("relationships") if isinstance(payload, dict) else None
    print(f"{indent}keys: {_sorted_keys(payload)}")
    if isinstance(attrs, dict):
        print(f"{indent}attribute_keys: {_sorted_keys(attrs)}")
    if isinstance(relationships, dict):
        print(f"{indent}relationship_keys: {_sorted_keys(relationships)}")
    matches = _candidate_paths(payload)
    if matches:
        print(f"{indent}candidate_status_paths:")
        for path, value in matches:
            if show_values:
                print(f"{indent}  {path}: {json.dumps(value, default=str)}")
            else:
                print(f"{indent}  {path}")


def _candidate_paths(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    matches: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if any(fragment in key_text.lower() for fragment in STATUS_KEY_FRAGMENTS):
                matches.append((path, child))
            if isinstance(child, dict):
                matches.extend(_candidate_paths(child, path))
            elif isinstance(child, list):
                for index, item in enumerate(child[:3]):
                    matches.extend(_candidate_paths(item, f"{path}[{index}]"))
    return matches


def _extract_collection(payload: Any) -> list[dict[str, Any]]:
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


def _has_next_page(payload: Any, current_page: int, item_count: int) -> bool:
    if not isinstance(payload, dict) or item_count == 0:
        return False
    links = payload.get("links")
    if isinstance(links, dict) and links.get("next"):
        return True
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return item_count >= DEFAULT_PAGE_SIZE
    last_page = _int_or_none(meta.get("last_page") or meta.get("total_pages"))
    if last_page is not None:
        return current_page < last_page
    total = _int_or_none(meta.get("total"))
    per_page = _int_or_none(meta.get("per_page")) or DEFAULT_PAGE_SIZE
    return bool(total is not None and current_page * per_page < total)


def _sorted_keys(value: dict[str, Any]) -> list[str]:
    return sorted(str(key) for key in value)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: Any) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
