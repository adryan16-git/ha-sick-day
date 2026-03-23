"""Core sick day logic: activate, deactivate, extend."""

import logging
from datetime import date, timedelta

from sick_day_helper import ha_api, config_manager
from sick_day_helper.constants import (
    ENTITY_ACTIVE,
    NOTIFICATION_CONFIRMATION,
    NOTIFICATION_EXPIRATION,
)

logger = logging.getLogger(__name__)


def _resolve_person_entity(display_name):
    """Resolve a friendly display name back to a person.* entity ID.

    Checks the mapping keys and matches by friendly name via the API.
    """
    mapping = config_manager.load_mapping()

    # Direct match (entity ID used as display name)
    if display_name in mapping:
        return display_name

    # Match by friendly name
    for person_id in mapping:
        try:
            state = ha_api.get_state(person_id)
            if state and state.get("attributes", {}).get("friendly_name") == display_name:
                return person_id
        except Exception:
            continue

    return None


def _friendly(entity_id):
    """Return the friendly name for an entity, falling back to the entity ID."""
    try:
        st = ha_api.get_state(entity_id)
        return st.get("attributes", {}).get("friendly_name", entity_id) if st else entity_id
    except Exception:
        return entity_id


def _restore_entity_states(entity_state_overrides, context=""):
    """Restore entity states from overrides recorded during activation."""
    for override in entity_state_overrides:
        entity_id = override.get("entity_id")
        previous_state = override.get("previous_state")
        if not entity_id or previous_state is None:
            continue
        try:
            ha_api.apply_entity_state(entity_id, previous_state)
            logger.info("%sRestored entity %s to %s", context, entity_id, previous_state)
        except Exception:
            logger.exception("%sFailed to restore entity %s to %s", context, entity_id, previous_state)


def activate_sick_day(person_display_name, end_date_str):
    """Activate a sick day for a person.

    Args:
        person_display_name: The friendly name or entity ID of the person.
        end_date_str: ISO date string (YYYY-MM-DD) for when the sick day ends.

    Returns True on success.
    """
    person_id = _resolve_person_entity(person_display_name)
    if not person_id:
        logger.error("Cannot resolve person: %s", person_display_name)
        ha_api.send_persistent_notification(
            title="Sick Day Helper — Error",
            message=f"Could not find person '{person_display_name}' in mapping.",
            notification_id=NOTIFICATION_CONFIRMATION,
        )
        return False

    person_entry = config_manager.load_mapping().get(person_id, {})
    automations = person_entry.get("automations", [])
    entity_states_config = person_entry.get("entity_states", [])

    if not automations and not entity_states_config:
        logger.warning("No automations or entity states mapped for %s", person_id)
        ha_api.send_persistent_notification(
            title="Sick Day Helper",
            message=f"No automations or entity states are mapped for {person_display_name}. Edit `/config/.sick_day_helper/mapping.json` to add mappings.",
            notification_id=NOTIFICATION_CONFIRMATION,
        )
        return False

    # Build lookup of automations already disabled by other active sick days
    active_state = config_manager.load_state()
    already_disabled_by = {}  # auto_id -> person_id that has it disabled
    for other_pid, other_entry in active_state.items():
        if other_pid == person_id:
            continue
        for auto_id in other_entry.get("disabled_automations", []):
            already_disabled_by[auto_id] = other_pid

    # Only disable automations that are currently enabled
    actually_disabled = []
    shared = []   # (auto_id, other_person_id)
    skipped = []  # (auto_id, reason)
    failed = []   # (auto_id,)
    for auto_id in automations:
        try:
            state = ha_api.get_state_value(auto_id)
            if state == "on":
                ha_api.turn_off(auto_id)
                actually_disabled.append(auto_id)
                logger.info("Disabled automation: %s", auto_id)
            elif auto_id in already_disabled_by:
                shared.append((auto_id, already_disabled_by[auto_id]))
                logger.info("Shared automation %s (already off via %s)", auto_id, already_disabled_by[auto_id])
            else:
                skipped.append((auto_id, state))
                logger.info("Skipped %s (state: %s)", auto_id, state)
        except Exception:
            failed.append(auto_id)
            logger.exception("Failed to disable %s", auto_id)

    # Apply entity state overrides
    entity_state_overrides = []
    entity_applied = []
    entity_failed = []
    for es in entity_states_config:
        entity_id = es.get("entity_id")
        target_state = es.get("state")
        if not entity_id or not target_state:
            continue
        try:
            previous_state = ha_api.get_state_value(entity_id)
            ha_api.apply_entity_state(entity_id, target_state)
            entity_state_overrides.append({
                "entity_id": entity_id,
                "target_state": target_state,
                "previous_state": previous_state,
            })
            entity_applied.append(entity_id)
            logger.info("Set entity %s to %s (was %s)", entity_id, target_state, previous_state)
        except Exception:
            entity_failed.append(entity_id)
            logger.exception("Failed to set entity %s to %s", entity_id, target_state)

    # Record state
    config_manager.set_person_state(person_id, end_date_str, actually_disabled, entity_state_overrides)

    # Update active indicator
    ha_api.turn_on(ENTITY_ACTIVE)

    # Build confirmation notification
    msg_parts = [f"Sick day activated for **{person_display_name}** until **{end_date_str}**."]

    msg_parts.append(f"\nDisabled automations ({len(actually_disabled)}):")
    msg_parts.append("\n".join(f"- {_friendly(a)}" for a in actually_disabled) if actually_disabled else "_(none)_")

    if shared:
        shared_lines = [f"- {_friendly(a)} _(shared with {_friendly(other_pid)})_" for a, other_pid in shared]
        msg_parts.append(f"\nAlready paused ({len(shared)}):")
        msg_parts.append("\n".join(shared_lines))

    if skipped:
        msg_parts.append(f"\nSkipped ({len(skipped)}):")
        msg_parts.append("\n".join(f"- {_friendly(a)} _(was {reason})_" for a, reason in skipped))

    if failed:
        msg_parts.append(f"\nFailed ({len(failed)}):")
        msg_parts.append("\n".join(f"- {_friendly(a)}" for a in failed))

    if entity_applied:
        msg_parts.append(f"\nEntity states applied ({len(entity_applied)}):")
        msg_parts.append("\n".join(f"- {_friendly(e)}" for e in entity_applied))

    if entity_failed:
        msg_parts.append(f"\nEntity state failures ({len(entity_failed)}):")
        msg_parts.append("\n".join(f"- {_friendly(e)}" for e in entity_failed))

    ha_api.send_persistent_notification(
        title="Sick Day Helper — Activated",
        message="\n".join(msg_parts),
        notification_id=NOTIFICATION_CONFIRMATION,
    )

    logger.info(
        "Sick day activated for %s until %s (%d automations disabled, %d entity states applied)",
        person_id, end_date_str, len(actually_disabled), len(entity_applied),
    )
    return True


def deactivate_sick_day(person_id):
    """Deactivate a sick day: re-enable automations, restore entity states, clear state.

    Only re-enables automations that aren't still needed by another active sick day.
    """
    person_state = config_manager.get_person_state(person_id)
    if not person_state:
        logger.warning("No active sick day for %s", person_id)
        return False

    disabled_by_this = set(person_state.get("disabled_automations", []))
    entity_state_overrides = person_state.get("entity_state_overrides", [])

    # Remove this person's state first so get_all_currently_disabled excludes them
    config_manager.remove_person_state(person_id)

    # Check which automations are still needed by other active sick days
    still_needed = config_manager.get_all_currently_disabled()
    to_reenable = disabled_by_this - still_needed

    for auto_id in to_reenable:
        try:
            ha_api.turn_on(auto_id)
            logger.info("Re-enabled automation: %s", auto_id)
        except Exception:
            logger.exception("Failed to re-enable %s", auto_id)

    kept_off = disabled_by_this & still_needed
    if kept_off:
        logger.info("Kept %d automation(s) off (still needed by other sick days): %s",
                    len(kept_off), kept_off)

    # Restore entity states
    _restore_entity_states(entity_state_overrides)

    # Update active indicator
    if not config_manager.has_active_sick_days():
        ha_api.turn_off(ENTITY_ACTIVE)

    # Dismiss expiration notification
    try:
        ha_api.dismiss_persistent_notification(NOTIFICATION_EXPIRATION)
    except Exception:
        pass

    try:
        state = ha_api.get_state(person_id)
        name = state.get("attributes", {}).get("friendly_name", person_id) if state else person_id
    except Exception:
        name = person_id

    ha_api.send_persistent_notification(
        title="Sick Day Helper — Cancelled",
        message=(
            f"Sick day cancelled for **{name}**. "
            f"{len(to_reenable)} automation(s) re-enabled, "
            f"{len(entity_state_overrides)} entity state(s) restored."
        ),
        notification_id=NOTIFICATION_CONFIRMATION,
    )

    logger.info("Sick day deactivated for %s (%d re-enabled, %d entity states restored)",
                person_id, len(to_reenable), len(entity_state_overrides))
    return True


def extend_sick_day(person_display_name, new_end_date_str):
    """Extend an existing sick day with a new end date."""
    person_id = _resolve_person_entity(person_display_name)
    if not person_id:
        logger.error("Cannot resolve person for extend: %s", person_display_name)
        return False

    person_state = config_manager.get_person_state(person_id)
    if not person_state:
        logger.warning("No active sick day to extend for %s", person_id)
        return False

    old_end = person_state["end_date"]
    config_manager.set_person_state(
        person_id,
        new_end_date_str,
        person_state["disabled_automations"],
        person_state.get("entity_state_overrides", []),
    )

    try:
        ha_api.dismiss_persistent_notification(NOTIFICATION_EXPIRATION)
    except Exception:
        pass

    try:
        state = ha_api.get_state(person_id)
        name = state.get("attributes", {}).get("friendly_name", person_id) if state else person_id
    except Exception:
        name = person_id

    ha_api.send_persistent_notification(
        title="Sick Day Helper — Extended",
        message=f"Sick day for **{name}** extended from {old_end} to **{new_end_date_str}**.",
        notification_id=NOTIFICATION_CONFIRMATION,
    )

    logger.info("Sick day extended for %s: %s -> %s", person_id, old_end, new_end_date_str)
    return True


def check_expirations():
    """Check for expired sick days, auto-re-enable automations, restore entity states, and notify."""
    state = config_manager.load_state()
    today = date.today().isoformat()
    expired = []

    for person_id, entry in state.items():
        if entry.get("end_date", "") <= today:
            expired.append(person_id)

    if not expired:
        return

    lines = ["The following sick day(s) have expired and automations have been re-enabled:\n"]
    for person_id in expired:
        try:
            st = ha_api.get_state(person_id)
            name = st.get("attributes", {}).get("friendly_name", person_id) if st else person_id
        except Exception:
            name = person_id

        entry = state[person_id]
        disabled_by_this = set(entry.get("disabled_automations", []))
        entity_state_overrides = entry.get("entity_state_overrides", [])

        # Remove this person's state so shared-automation check excludes them
        config_manager.remove_person_state(person_id)

        # Only re-enable automations not still needed by another active sick day
        still_needed = config_manager.get_all_currently_disabled()
        to_reenable = disabled_by_this - still_needed
        kept_off = disabled_by_this & still_needed

        actually_reenabled = []
        failed_reenable = []
        for auto_id in to_reenable:
            try:
                ha_api.turn_on(auto_id)
                actually_reenabled.append(auto_id)
                logger.info("Re-enabled automation (expired): %s", auto_id)
            except Exception:
                failed_reenable.append(auto_id)
                logger.exception("Failed to re-enable %s", auto_id)

        # Restore entity states
        _restore_entity_states(entity_state_overrides, context=f"[{person_id}] ")

        summary = f"- **{name}** (ended {entry['end_date']}) — {len(actually_reenabled)} automation(s) re-enabled"
        if entity_state_overrides:
            summary += f", {len(entity_state_overrides)} entity state(s) restored"
        lines.append(summary)
        if kept_off:
            lines.append(f"  - {len(kept_off)} automation(s) kept off (still needed by another sick day)")
            logger.info("Kept %d automation(s) off for %s (shared): %s", len(kept_off), person_id, kept_off)
        if failed_reenable:
            failed_names = ", ".join(_friendly(a) for a in failed_reenable)
            lines.append(f"  - WARNING: {len(failed_reenable)} automation(s) failed to re-enable and may still be off: {failed_names}")
            logger.error("Failed to re-enable %d automation(s) for %s: %s", len(failed_reenable), person_id, failed_reenable)

    # Update active indicator
    if not config_manager.has_active_sick_days():
        ha_api.turn_off(ENTITY_ACTIVE)

    ha_api.send_persistent_notification(
        title="Sick Day Helper — Expired",
        message="\n".join(lines),
        notification_id=NOTIFICATION_EXPIRATION,
    )

    logger.info("Expired sick days auto-deactivated: %s", expired)


def verify_state_on_startup():
    """On startup, verify that automations recorded as disabled are still off.

    If an automation was manually re-enabled, remove it from state tracking.
    """
    state = config_manager.load_state()
    changed = False

    for person_id, entry in state.items():
        still_disabled = []
        for auto_id in entry.get("disabled_automations", []):
            try:
                current = ha_api.get_state_value(auto_id)
                if current == "off":
                    still_disabled.append(auto_id)
                else:
                    logger.info("Automation %s was re-enabled externally, removing from tracking", auto_id)
                    changed = True
            except Exception:
                # Keep it in the list if we can't check
                still_disabled.append(auto_id)

        if len(still_disabled) != len(entry.get("disabled_automations", [])):
            entry["disabled_automations"] = still_disabled
            changed = True

    if changed:
        config_manager.save_state(state)
        logger.info("State updated after startup verification")
