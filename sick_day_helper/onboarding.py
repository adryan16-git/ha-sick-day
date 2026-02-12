"""First-run onboarding: discover people/automations, suggest mapping."""

import logging
import re

from sick_day_helper import ha_api, config_manager
from sick_day_helper.constants import (
    ENTITY_PERSON_SELECT,
    ENTITY_SETUP_COMPLETE,
    NOTIFICATION_ONBOARDING,
)

logger = logging.getLogger(__name__)


def _extract_name_tokens(entity_id):
    """Extract name tokens from an entity ID for fuzzy matching.

    'person.kid_1' -> {'kid', '1', 'kid_1'}
    'automation.kid_1_morning_routine' -> {'kid', '1', 'kid_1', 'morning', 'routine'}
    """
    name_part = entity_id.split(".", 1)[1] if "." in entity_id else entity_id
    tokens = set(re.split(r"[_\s]+", name_part.lower()))
    # Also add two-token combinations for better matching
    parts = re.split(r"[_\s]+", name_part.lower())
    for i in range(len(parts) - 1):
        tokens.add(f"{parts[i]}_{parts[i + 1]}")
    return tokens


def _suggest_mapping(people, automations):
    """Auto-suggest person-to-automation mapping based on name matching.

    For each person, find automations whose name contains the person's name tokens.
    """
    mapping = {}
    for person_id in people:
        person_tokens = _extract_name_tokens(person_id)
        # Use the most specific token (longest) for matching
        # Skip very short/generic tokens
        match_tokens = {t for t in person_tokens if len(t) > 1}

        matched = []
        for auto_id in automations:
            auto_tokens = _extract_name_tokens(auto_id)
            # Check if any person token appears in the automation name
            if match_tokens & auto_tokens:
                matched.append(auto_id)

        mapping[person_id] = sorted(matched)

    return mapping


def run_onboarding():
    """Run the onboarding process.

    1. Discover person.* and automation.* entities
    2. Auto-suggest mapping by name matching
    3. Save mapping
    4. Populate the person dropdown
    5. Send a notification explaining the mapping

    Returns True if onboarding completed, False if it failed.
    """
    logger.info("Starting onboarding...")

    try:
        all_states = ha_api.get_states()
    except Exception:
        logger.exception("Failed to fetch states during onboarding")
        return False

    people = sorted(
        s["entity_id"] for s in all_states
        if s["entity_id"].startswith("person.")
    )
    automations = sorted(
        s["entity_id"] for s in all_states
        if s["entity_id"].startswith("automation.")
    )

    logger.info("Discovered %d person(s) and %d automation(s)", len(people), len(automations))

    if not people:
        ha_api.send_persistent_notification(
            title="Sick Day Helper — Setup",
            message=(
                "No `person.*` entities found. Please create Person entities in "
                "Home Assistant before using Sick Day Helper."
            ),
            notification_id=NOTIFICATION_ONBOARDING,
        )
        return False

    # Generate suggested mapping
    mapping = _suggest_mapping(people, automations)
    config_manager.save_mapping(mapping)

    # Populate the person dropdown
    friendly_names = []
    for person_id in people:
        state = ha_api.get_state(person_id)
        name = state.get("attributes", {}).get("friendly_name", person_id) if state else person_id
        friendly_names.append(name)

    if friendly_names:
        ha_api.set_input_select_options(ENTITY_PERSON_SELECT, friendly_names)

    # Build notification message
    lines = ["Sick Day Helper has auto-detected the following mapping:\n"]
    for person_id in people:
        state = ha_api.get_state(person_id)
        name = state.get("attributes", {}).get("friendly_name", person_id) if state else person_id
        autos = mapping.get(person_id, [])
        if autos:
            auto_list = "\n".join(f"  - `{a}`" for a in autos)
            lines.append(f"**{name}** (`{person_id}`):\n{auto_list}\n")
        else:
            lines.append(f"**{name}** (`{person_id}`): _(no automations matched)_\n")

    lines.append(
        "To edit this mapping, modify the file:\n"
        "`/config/.sick_day_helper/mapping.json`\n\n"
        "Then restart the add-on to apply changes."
    )

    ha_api.send_persistent_notification(
        title="Sick Day Helper — Setup Complete",
        message="\n".join(lines),
        notification_id=NOTIFICATION_ONBOARDING,
    )

    # Mark setup complete
    try:
        ha_api.turn_on(ENTITY_SETUP_COMPLETE)
    except Exception:
        logger.debug("Could not set setup_complete flag (entity may not exist yet)")

    logger.info("Onboarding complete")
    return True
