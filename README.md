# Hospitable Integration for Home Assistant

Custom Home Assistant integration for Hospitable Public API v2.

## Features

- Current guest sensors per Hospitable property.
- Next guest sensors per property.
- Upcoming guest count sensors with reservation details in attributes.
- Current and next reservation detail sensors for UUID, code, check-in, check-out, status, and platform.
- `hospitable_api.post_guest_message` service/action for automations.
- Personal Access Token setup through the Home Assistant UI.
- Paginated reservation/property fetches with normalized common Hospitable response shapes.

## Installation

### HACS Custom Repository

1. In HACS, open **Custom repositories**.
2. Add this repository URL.
3. Select **Integration** as the category.
4. Install **Hospitable Integration**.
5. Restart Home Assistant.
6. Go to **Settings -> Devices & services -> Add integration**.
7. Search for **Hospitable Integration**.
8. Enter a Hospitable Personal Access Token.

### Manual Installation

1. Copy `custom_components/hospitable_api` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings -> Devices & services -> Add integration**.
4. Search for **Hospitable Integration**.
5. Enter a Hospitable Personal Access Token.

## HACS Readiness

This repository is structured for HACS as a custom integration repository:

- `hacs.json` is present at the repository root.
- The integration lives under `custom_components/hospitable_api`.
- `manifest.json` includes the HACS-required `domain`, `documentation`, `issue_tracker`, `codeowners`, `name`, and `version` keys.
- GitHub Actions are included for HACS validation and Hassfest validation.
- Local brand assets are included under `custom_components/hospitable_api/brand`.

The public GitHub repository, GitHub Issues, repository topics, MIT license, and
release are in place. The repository installs as a custom HACS integration.
External `home-assistant/brands` submission is optional and only needed for HACS
default repository inclusion.

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

You can also pass `reservation_uuid` directly. Provide either `entity_id` or
`reservation_uuid`, not both:

```yaml
actions:
  - action: hospitable_api.post_guest_message
    data:
      reservation_uuid: "your-reservation-uuid"
      message: "Your custom message"
```

## Documentation

- [Notes](https://github.com/peluke/hospitableIntegration/wiki/Notes)
- [Troubleshooting](https://github.com/peluke/hospitableIntegration/wiki/Troubleshooting)
- [First Arrival Blueprint](https://github.com/peluke/hospitableIntegration/wiki/First-Arrival-Blueprint)

Blueprint import URL:

```text
https://raw.githubusercontent.com/peluke/hospitableIntegration/main/blueprints/automation/hospitable_api/guest_first_arrival.yaml
```
