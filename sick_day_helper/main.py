"""Sick Day Helper — Main entry point and poll loop."""

import logging
import os
import sys
import time
from datetime import date, timedelta

from sick_day_helper import ha_api, config_manager
from sick_day_helper.constants import (
    ENTITY_SUBMIT,
    ENTITY_CANCEL,
    ENTITY_EXTEND,
    ENTITY_PERSON_SELECT,
    ENTITY_DURATION_TYPE,
    ENTITY_NUM_DAYS,
    ENTITY_END_DATE,
    DURATION_NUM_DAYS,
    POLL_INTERVAL,
    LOG_LEVEL,
)
from sick_day_helper.package_installer import install_package
from sick_day_helper.onboarding import run_onboarding
from sick_day_helper.sick_day_manager import (
    activate_sick_day,
    deactivate_sick_day,
    extend_sick_day,
    check_expirations,
    verify_state_on_startup,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("sick_day_helper")


def _compute_end_date():
    """Compute the end date from the input helper entities."""
    duration_type = ha_api.get_state_value(ENTITY_DURATION_TYPE)

    if duration_type == DURATION_NUM_DAYS:
        num_days_str = ha_api.get_state_value(ENTITY_NUM_DAYS)
        try:
            num_days = int(float(num_days_str))
        except (TypeError, ValueError):
            num_days = 1
        return (date.today() + timedelta(days=num_days)).isoformat()
    else:
        # "Until Date" — read the datetime entity
        end_date = ha_api.get_state_value(ENTITY_END_DATE)
        if end_date and end_date != "unknown":
            return end_date
        # Fallback: 1 day
        return (date.today() + timedelta(days=1)).isoformat()


def _reset_toggle(entity_id):
    """Turn off a toggle after processing it."""
    try:
        ha_api.turn_off(entity_id)
    except Exception:
        logger.debug("Could not reset toggle %s", entity_id)


def _resolve_active_person_for_cancel():
    """Find the person to cancel based on the selected person or the only active one."""
    selected = ha_api.get_state_value(ENTITY_PERSON_SELECT)
    state = config_manager.load_state()

    if not state:
        return None

    # Try to match selected person
    mapping = config_manager.load_mapping()
    for person_id in state:
        try:
            person_state = ha_api.get_state(person_id)
            friendly = person_state.get("attributes", {}).get("friendly_name", person_id) if person_state else person_id
        except Exception:
            friendly = person_id

        if friendly == selected or person_id == selected:
            return person_id

    # If only one active, use that
    if len(state) == 1:
        return next(iter(state))

    return None


def handle_submit():
    """Handle the submit toggle being turned on."""
    logger.info("Submit triggered")
    person_name = ha_api.get_state_value(ENTITY_PERSON_SELECT)
    if not person_name or person_name == "(none)":
        logger.warning("No person selected, ignoring submit")
        _reset_toggle(ENTITY_SUBMIT)
        return

    end_date = _compute_end_date()
    activate_sick_day(person_name, end_date)
    _reset_toggle(ENTITY_SUBMIT)


def handle_cancel():
    """Handle the cancel toggle being turned on."""
    logger.info("Cancel triggered")
    person_id = _resolve_active_person_for_cancel()
    if person_id:
        deactivate_sick_day(person_id)
    else:
        logger.warning("Could not determine which sick day to cancel")
    _reset_toggle(ENTITY_CANCEL)


def handle_extend():
    """Handle the extend toggle being turned on."""
    logger.info("Extend triggered")
    person_name = ha_api.get_state_value(ENTITY_PERSON_SELECT)
    if not person_name or person_name == "(none)":
        logger.warning("No person selected, ignoring extend")
        _reset_toggle(ENTITY_EXTEND)
        return

    end_date = _compute_end_date()
    extend_sick_day(person_name, end_date)
    _reset_toggle(ENTITY_EXTEND)


def startup():
    """Run startup tasks."""
    logger.info("Sick Day Helper starting up...")

    # Ensure data directory exists
    config_manager.ensure_data_dir()

    # Install/update the HA package YAML
    if install_package():
        logger.info("Package YAML installed — HA may need a restart to pick up new entities")

    # Run onboarding if no mapping exists
    if not config_manager.mapping_exists():
        logger.info("No mapping found, running onboarding...")
        run_onboarding()
    else:
        logger.info("Mapping exists with %d person(s)", len(config_manager.load_mapping()))

    # Verify state consistency on startup
    if config_manager.has_active_sick_days():
        logger.info("Active sick days found, verifying state...")
        verify_state_on_startup()
        check_expirations()


def poll_loop():
    """Main poll loop — check for user actions and expirations."""
    last_expiration_check = 0
    expiration_check_interval = 300  # Check expirations every 5 minutes

    while True:
        try:
            # Check submit toggle
            submit_state = ha_api.get_state_value(ENTITY_SUBMIT)
            if submit_state == "on":
                handle_submit()

            # Check cancel toggle
            cancel_state = ha_api.get_state_value(ENTITY_CANCEL)
            if cancel_state == "on":
                handle_cancel()

            # Check extend toggle
            extend_state = ha_api.get_state_value(ENTITY_EXTEND)
            if extend_state == "on":
                handle_extend()

            # Periodic expiration check
            now = time.time()
            if now - last_expiration_check >= expiration_check_interval:
                if config_manager.has_active_sick_days():
                    check_expirations()
                last_expiration_check = now

        except Exception:
            logger.exception("Error in poll loop")

        time.sleep(POLL_INTERVAL)


def main():
    """Entry point."""
    startup()
    logger.info("Entering poll loop (interval=%ds)", POLL_INTERVAL)
    poll_loop()


if __name__ == "__main__":
    main()
