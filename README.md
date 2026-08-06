# Hospitable API for Home Assistant

Custom Home Assistant integration for Hospitable Public API v2.

## Features

- Current guest sensors per Hospitable property.
- Next guest sensors per property.
- Upcoming guest count sensors with reservation details in attributes.
- Current and next reservation detail sensors for UUID, code, check-in, check-out, status, and platform.
- `hospitable_api.post_guest_message` service/action for automations.
- Personal Access Token setup through the Home Assistant UI.

## Installation

### HACS Custom Repository

1. In HACS, open **Custom repositories**.
2. Add this repository URL.
3. Select **Integration** as the category.
4. Install **Hospitable API**.
5. Restart Home Assistant.
6. Go to **Settings -> Devices & services -> Add integration**.
7. Search for **Hospitable API**.
8. Enter a Hospitable Personal Access Token.

### Manual Installation

1. Copy `custom_components/hospitable_api` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings -> Devices & services -> Add integration**.
4. Search for **Hospitable API**.
5. Enter a Hospitable Personal Access Token.

## HACS Readiness

This repository is structured for HACS as a custom integration repository:

- `hacs.json` is present at the repository root.
- The integration lives under `custom_components/hospitable_api`.
- `manifest.json` includes the HACS-required `domain`, `documentation`, `issue_tracker`, `codeowners`, `name`, and `version` keys.
- GitHub Actions are included for HACS validation and Hassfest validation.
- Local brand assets are included under `custom_components/hospitable_api/brand`.

## Icon

The integration icon is an original mark inspired by the project context: a guest reservation card, a pink guest badge, and automation nodes. SVG source files live in `assets/`, with Home Assistant-ready PNG assets in `custom_components/hospitable_api/brand/`.

Before publishing broadly:

- Create a public GitHub repository.
- Add repository topics such as `hacs`, `home-assistant`, `homeassistant`, and `custom-integration`.
- Enable GitHub Issues.
- Add the integration to `home-assistant/brands` if you want it to meet HACS default repository inclusion requirements.
- Create a GitHub release for each version you want HACS users to install explicitly.

## Example Automation

```yaml
alias: Message current guest when door unlocks
triggers:
  - trigger: state
    entity_id: lock.front_door
    to: unlocked
actions:
  - action: hospitable_api.post_guest_message
    data:
      entity_id: sensor.hospitable_cabin_current_guest
      message: "The front door was unlocked. Let us know if you need anything."
```

You can also pass `reservation_uuid` directly:

```yaml
actions:
  - action: hospitable_api.post_guest_message
    data:
      reservation_uuid: "your-reservation-uuid"
      message: "Your custom message"
```

## Notes

- Store Hospitable tokens only through the Home Assistant config flow.
- The integration polls every 15 minutes.
- Hospitable reservation lookups require property UUIDs. If you leave the property field blank, the integration uses the UUIDs returned by the `/properties` endpoint.
- Guest lists are exposed as sensor attributes because Home Assistant sensor states must be scalar values.
- Version `0.1.6` adds separate current and next reservation detail sensors so automations can use scalar entity states instead of parsing attributes.

## Troubleshooting

### Setup succeeds but no entities appear

Version `0.1.1` could create zero sensors when the configured property ID did not exactly match the primary ID returned by `/properties`, even though reservation requests succeeded. Upgrade to `0.1.2` or later. The integration now keeps all known property aliases and creates placeholder property devices for configured IDs when `/properties` does not return a matching record.

### Entities appear but guest data is empty

Upgrade to `0.1.5` or later. The integration now resolves configured property aliases back to Hospitable property UUIDs before querying reservations, parses Hospitable's `check_in`, `check_out`, `guests`, `properties`, and `reservation_status` response fields, and exposes diagnostic attributes on every sensor.

Check these attributes on any Hospitable sensor:

- `hospitable_reservation_count`
- `hospitable_matched_reservation_count`
- `hospitable_queried_property_uuids`
- `hospitable_reservation_property_ids`
- `hospitable_reservation_date_samples`

### Failed setup, will retry: 400 Bad Request

Version `0.1.0` sent reservation property filters as a comma-separated `properties` query parameter. Hospitable expects repeated `properties[]` query parameters. Upgrade to `0.1.1` or later, restart Home Assistant, and reload the integration.

If the error persists, confirm that the optional property field contains Hospitable property UUIDs, not numeric property IDs or listing IDs.
