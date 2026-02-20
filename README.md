# Sick Day Helper

A Home Assistant add-on for managing automations when schedules change.

If you have automations that run daily or trigger from other typical daily schedules, those automations might need to change if your daily routine changes. Enter Sick Day Helper. Did your kid get sick last night, and now you want them to sleep in and not have lights turn on and wake them up, or notifications run? No problem, set a sick day. It's kind of like vacation mode for the people and areas in your Home Assistant.

## Features

- **Per-person automation control** — Map each household member to their automations, then disable them all with one action.
- **Flexible duration** — Set a sick day by number of days or pick a specific end date.
- **Automatic expiration** — Automations are re-enabled when the sick day ends, with a notification summary.
- **Extend or cancel** — Adjust an active sick day without starting over.
- **Shared automation safety** — If two people share an automation and only one recovers, it stays off until both are done.
- **Setup wizard** — An ingress UI walks you through mapping people to automations, with auto-suggestions based on name matching, areas, and labels.

## Installation

1. In Home Assistant, go to **Settings > Add-ons > Add-on Store**.
2. Open the three-dot menu and select **Repositories**.
3. Add this repository URL.
4. Find **Sick Day Helper** in the store and click **Install**.
5. Start the add-on — it will appear in your sidebar.

## How It Works

### Setup

On first start, the add-on creates input helper entities (person selector, duration picker, submit/cancel/extend toggles) and sends a notification directing you to the setup wizard in the sidebar.

The wizard discovers all people and automations in your HA instance, groups them by area and label, and helps you build a **mapping** — which automations should be disabled when a given person has a sick day. It auto-suggests matches based on entity names. You can edit the mapping any time through the UI.

### Using it

1. Select a person and duration, then toggle **Submit**.
2. The add-on disables the person's mapped automations (only ones currently enabled — it won't touch automations you've already turned off manually).
3. A confirmation notification lists what was disabled.

When the sick day expires, automations are automatically re-enabled. You can also **Extend** to push the end date forward, or **Cancel** to end early and re-enable everything immediately.

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `LOG_LEVEL` | `info` | Set to `debug` for verbose logging. |
