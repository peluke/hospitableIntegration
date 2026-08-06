# Hospitable API

Home Assistant custom integration for Hospitable Public API v2.

This integration creates per-property guest sensors for the current guest, next guest, and upcoming guest count. It also adds the `hospitable_api.post_guest_message` service/action so Home Assistant automations can send a message to a guest by reservation UUID or by using a Hospitable guest sensor entity.

