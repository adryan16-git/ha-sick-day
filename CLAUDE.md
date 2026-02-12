# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant add-on ("Sick Day Helper") that manages automations when schedules change. When a user declares a sick day for a person, the add-on disables that person's mapped automations and notifies when the sick day expires.

## Architecture

- **Entrypoint**: `run.sh` — thin bash launcher that reads HA config options, then `exec python3 /sick_day_helper/main.py`.
- **Python service** (`sick_day_helper/`): Core logic with a 10-second poll loop.
  - `main.py` — Entry point, startup tasks, poll loop that watches input helper toggles.
  - `ha_api.py` — HA REST API wrapper using `urllib.request` (stdlib, no pip deps). Talks to `http://supervisor/core/api` via `SUPERVISOR_TOKEN`.
  - `config_manager.py` — Read/write `mapping.json` (person→automation map) and `state.json` (active sick days) in `/config/.sick_day_helper/`.
  - `sick_day_manager.py` — Activate/deactivate/extend sick day logic. Only records automations it actually turns off; checks for shared automations before re-enabling.
  - `onboarding.py` — First-run: discovers `person.*` and `automation.*` entities, auto-suggests mapping by name matching, sends setup notification.
  - `package_installer.py` — Copies `packages/sick_day_helper.yaml` to `/config/packages/` for HA to load input helpers.
  - `constants.py` — Entity IDs, file paths, intervals.
- **HA Package** (`packages/sick_day_helper.yaml`): Defines input_select, input_number, input_datetime, and input_boolean entities used as the user-facing form.
- **Container**: `Dockerfile` builds from HA's dynamic base image (`BUILD_FROM` arg), installs Python3/pip, copies Python code and packages.
- **Add-on config**: `config.json` defines metadata, schema options, `homeassistant_api: true` for API access.

## Configuration Options

Exposed via Home Assistant's WebUI and passed as environment variables:
- `LOG_LEVEL` — `info` or `debug`
- `enable_heartbeat` / `ENABLE_HEARTBEAT` — boolean toggle for heartbeat logging

## Data Files (runtime, in `/config/.sick_day_helper/`)

- `mapping.json` — Person-to-automation mapping (created during onboarding, user-editable).
- `state.json` — Active sick day state (tracks who is sick and which automations were disabled).

## Core Flow

1. **Submit**: User selects person + duration, toggles submit → automations disabled, state recorded, confirmation notification sent.
2. **Expiration**: Poll detects `end_date <= today` → persistent notification asking to cancel or extend (no auto-re-enable for safety).
3. **Extend**: User sets new duration, toggles extend → state updated, expiration notification cleared.
4. **Cancel**: User toggles cancel → automations re-enabled (respecting shared automations), state cleared.

## Building and Running

This add-on runs inside Home Assistant's Supervisor. There is no standalone build/test workflow.

- **Local Docker build**: `docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest -t sick-day .`
- **Deploy**: Add the GitHub repository URL (`https://github.com/adryan16-git/ha-sick-day`) as a custom add-on repository in Home Assistant, then install and start the add-on.
- **No test framework** is currently configured.

## Key Conventions

- Version is tracked in `config.json` (`"version"` field) — bump it on each release.
- The add-on starts with `"boot": "auto"` and `"startup": "services"` (background service, no init process).
- The container has read-write access to `/config` (Home Assistant's config directory).
- API calls use `urllib.request` (stdlib) — no pip dependencies beyond Python stdlib.
- Only automations that were actually on get recorded as disabled (prevents re-enabling intentionally disabled automations).
- Shared automations are protected: before re-enabling, check if another active sick day still needs it off.
