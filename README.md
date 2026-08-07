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
- Checkout-day task sensors for cleaning assignment coverage.
- Task-detail diagnostics for troubleshooting Hospitable task status fields.

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

### Upgrade Note

The user-facing name is Hospitable Integration. The Home Assistant domain
remains `hospitable_api` so existing config entries and automations continue to
load after upgrade.

## Automation Notes

Checkout task assignment alerts are exposed per property with the `Checkout
Task Alert` sensor. The sensor turns `on` when a checkout-day task assignment
is pending, unaccepted, rejected, cancelled, or unassigned. Tasks with unknown
assignment status are listed in attributes but do not trigger the alert.

Task diagnostics expose detail fetch counts, detail fetch errors, and sampled
response keys so field-shape issues can be debugged without publishing raw task
payloads.

The integration reads Hospitable's task `progress_status` and
`task_assignment.status` fields. Assignment alerts trigger for pending,
unaccepted, rejected, cancelled, or unassigned checkout tasks.

If the Hospitable task endpoint is unavailable for the token, the task sensors
still load as `0`/`off` and expose the API error in the
`hospitable_task_error` attribute. Task list requests intentionally avoid
unsupported per-task includes.

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
- [Task Attention Blueprint](https://github.com/peluke/hospitableIntegration/wiki/Task-Attention-Blueprint)
- [Task API Probe](https://github.com/peluke/hospitableIntegration/wiki/Task-API-Probe)

Blueprint import URLs:

```text
https://raw.githubusercontent.com/peluke/hospitableIntegration/main/blueprints/automation/hospitableIntegration/guest_first_arrival.yaml
https://raw.githubusercontent.com/peluke/hospitableIntegration/main/blueprints/automation/hospitableIntegration/checkout_task_attention.yaml
```
