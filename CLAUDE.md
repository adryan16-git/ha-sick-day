# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant add-on ("Sick Day Helper") that manages automations when schedules change. Runs as a containerized background service inside Home Assistant. Currently in early development — core sick-day logic is not yet implemented (placeholder in `run.sh`).

## Architecture

- **Entrypoint**: `run.sh` — bash script using `bashio` (HA's shell utility library). Runs an infinite loop with a 60-second sleep interval.
- **Container**: `Dockerfile` builds from HA's dynamic base image (`BUILD_FROM` arg), installs Python3/pip on Alpine Linux.
- **Add-on config**: `config.json` defines the add-on metadata, schema options (`enable_heartbeat`, `LOG_LEVEL`), environment variable mappings, and supported architectures (amd64, aarch64, armv7, armhf).
- **Repository metadata**: `repository.json` registers this as an HA add-on repository.

Python3 is installed in the container but no Python code exists yet. The service logic is entirely in bash for now.

## Configuration Options

Exposed via Home Assistant's WebUI and passed as environment variables:
- `LOG_LEVEL` — `info` or `debug`
- `enable_heartbeat` / `ENABLE_HEARTBEAT` — boolean toggle for heartbeat logging

## Building and Running

This add-on runs inside Home Assistant's Supervisor. There is no standalone build/test workflow.

- **Local Docker build**: `docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest -t sick-day .`
- **Deploy**: Add the GitHub repository URL (`https://github.com/adryan16-git/ha-sick-day`) as a custom add-on repository in Home Assistant, then install and start the add-on.
- **No test framework** is currently configured.

## Key Conventions

- Version is tracked in `config.json` (`"version"` field) — bump it on each release.
- The add-on starts with `"boot": "auto"` and `"startup": "services"` (background service, no init process).
- The container has read-write access to `/config` (Home Assistant's config directory).
