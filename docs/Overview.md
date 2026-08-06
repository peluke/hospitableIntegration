# Hospitable HA Plugin

## Purpose

Home Assistant custom integration for Hospitable Public API v2. It exposes current and upcoming guest reservation data as sensors and provides a service/action that automations can use to send guest messages.

## File Locations

- Source: `/Users/peluke/Documents/Hospitable HA Plugin`
- Home Assistant integration: `/Users/peluke/Documents/Hospitable HA Plugin/custom_components/hospitable_integration`
- Obsidian documentation: `/Users/peluke/Documents/ObsidianSync/hospitable-ha-plugin`

## Setup

### HACS Custom Repository

1. In HACS, open **Custom repositories**.
2. Add the GitHub repository URL.
3. Select **Integration** as the category.
4. Install **Hospitable Integration**.
5. Restart Home Assistant.
6. Add the integration from **Settings -> Devices & services**.
7. Enter a Hospitable Personal Access Token.

### Manual

1. Copy `custom_components/hospitable_integration` into Home Assistant's `custom_components` folder.
2. Restart Home Assistant.
3. Add the integration from **Settings -> Devices & services**.
4. Enter a Hospitable Personal Access Token.
5. Optionally limit polling to specific comma-separated property UUIDs.

## HACS Readiness

- Root `hacs.json` added.
- Repository contains one integration under `custom_components/hospitable_integration`.
- Manifest includes HACS-required metadata.
- GitHub Actions validation is configured for `hacs/action@main` and `home-assistant/actions/hassfest@master`.
- Local brand icon and logo assets are stored in `custom_components/hospitable_integration/brand`, with editable SVG source files in `assets`.

For default HACS repository inclusion later, the public GitHub repo will still need repository metadata, enabled issues, Home Assistant Brands submission, passing CI, and a GitHub release.

The repository validation workflow ignores HACS `brands` and `topics` checks for custom-HACS use because those depend on GitHub settings and the external `home-assistant/brands` repository, not files in this project. The repository license is MIT.

## Entities

Each Hospitable property gets:

- `Current Guest`: current in-house guest, with reservation details in attributes.
- `Next Guest`: next arrival, with reservation details in attributes.
- `Upcoming Guests`: count of upcoming reservations, with reservation list in attributes.
- `Checkout Tasks`: count of tasks that land on known checkout dates.
- `Checkout Task Alert`: `on` when a checkout-day task is pending, unaccepted, declined, or rejected.
- Current reservation detail sensors: reservation UUID, reservation code, check-in, check-out, status, and platform.
- Next reservation detail sensors: reservation UUID, reservation code, check-in, check-out, status, and platform.

## Automation Service

Service/action: `hospitable_integration.post_guest_message`

Required data:

- `message`

Use either:

- `reservation_uuid`
- `entity_id` for a Hospitable current or next guest sensor with a `reservation_uuid` attribute

## Blueprint

The repository includes a reusable automation blueprint at
`blueprints/automation/hospitableIntegration/guest_first_arrival.yaml`.

Use one automation instance per property/lock. Each instance watches a lock
entity, compares the active Hospitable reservation UUID with an `input_text`
helper, and sends a notification only once for each reservation.

Blueprint import URL:

```text
https://raw.githubusercontent.com/peluke/hospitableIntegration/main/blueprints/automation/hospitableIntegration/guest_first_arrival.yaml
```

## Security Notes

- Do not store Hospitable tokens in source files, YAML examples, or Obsidian notes.
- Use placeholders in examples.
- Home Assistant stores the token in the config entry created by the UI flow.

## Known Issues

- Hospitable Integration field shapes can vary by booking platform and included relationships; the integration normalizes common variants.
- Version `0.1.2` creates sensor entities for configured property IDs even when `/properties` returns a different primary ID shape.
- Hospitable reservation queries require property UUIDs. Version `0.1.1` sends these as repeated `properties[]` query parameters.
- The message endpoint is implemented as `POST /v2/reservations/{reservation_uuid}/messages` with a JSON `body` field based on current public API references. Confirm against live Hospitable docs if posting fails.

## Change Log

- 2026-08-06: Added checkout-day task fetches and per-property checkout task sensors for cleaning assignment coverage.
- 2026-08-06: Renamed the Home Assistant domain to `hospitable_integration`, moved the integration package, moved the blueprint folder, and updated service/action examples.
- 2026-08-06: Hardened API pagination, response normalization, service validation, first-arrival blueprint validation, sensor reservation indexing, config input cleanup, local tests, and reduced raw guest/API payload storage in coordinator state.
- 2026-08-06: Added a first-arrival automation blueprint for keypad unlock alerts per property.
- 2026-08-06: Moved README notes and troubleshooting content to GitHub Wiki pages and linked them from the README.
- 2026-08-06: Added MIT license and updated GitHub Actions checkout to Node 24-compatible v6.
- 2026-08-06: Adjusted HACS validation workflow to ignore external `brands` and `topics` checks for custom repository use.
- 2026-08-06: Changed icon/logo background to a full blue square so rendered PNG corners are not white.
- 2026-08-06: Reworked icon/logo into a Home Assistant-blue square with a bold underlined O in Hospitable pink.
- 2026-08-06: Reworked icon/logo into a reservation-card design using the same teal, cyan, white, and pink color scheme.
- 2026-08-06: Added current and next reservation detail sensors for UUID, code, check-in, check-out, status, and platform.
- 2026-08-06: Fixed empty guest sensors by querying reservations with resolved property UUIDs, parsing additional Hospitable reservation field shapes, requesting up to 100 reservations, and exposing diagnostic attributes.
- 2026-08-06: Updated icon/logo accent from yellow to Hospitable-style pink.
- 2026-08-06: Added original icon/logo brand assets inspired by the Hospitable and Home Assistant project contexts.
- 2026-08-06: Fixed zero-entity setup by preserving property aliases and creating placeholder properties for configured IDs without matching `/properties` records.
- 2026-08-06: Fixed reservation query parameters to use `properties[]`, added check-in/check-out reservation lookups, improved API error messages, and changed outbound guest message payload to `body`.
- 2026-08-06: Added HACS metadata, HACS install docs, and GitHub Actions validation workflow.
- 2026-08-06: Initial custom integration scaffold with guest sensors and guest-message service.
