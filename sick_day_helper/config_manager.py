"""Manages mapping.json and state.json for Sick Day Helper."""

import json
import logging
import os

from sick_day_helper.constants import DATA_DIR, MAPPING_FILE, STATE_FILE, WIZARD_STATE_FILE

logger = logging.getLogger(__name__)


def ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path):
    """Read and parse a JSON file, returning None if it doesn't exist."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        logger.error("Corrupt JSON file: %s", path)
        return None


def _write_json(path, data):
    """Write data to a JSON file atomically."""
    ensure_data_dir()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


# --- Mapping ---

def load_mapping():
    """Load the person-to-automation mapping.

    Returns dict like:
    {
        "person.kid_1": ["automation.kid_1_morning", "automation.kid_1_bedtime"],
        "person.kid_2": ["automation.kid_2_school"]
    }
    """
    return _read_json(MAPPING_FILE) or {}


def save_mapping(mapping):
    """Save the person-to-automation mapping."""
    _write_json(MAPPING_FILE, mapping)
    logger.info("Saved mapping with %d person(s)", len(mapping))


def mapping_exists():
    """Check if a mapping file exists."""
    return os.path.isfile(MAPPING_FILE)


# --- State ---

def load_state():
    """Load active sick day state.

    Returns dict like:
    {
        "person.kid_1": {
            "end_date": "2025-01-15",
            "disabled_automations": ["automation.kid_1_morning"]
        }
    }
    """
    return _read_json(STATE_FILE) or {}


def save_state(state):
    """Save active sick day state."""
    _write_json(STATE_FILE, state)


def get_person_state(person_entity_id):
    """Get the sick day state for a specific person."""
    state = load_state()
    return state.get(person_entity_id)


def set_person_state(person_entity_id, end_date, disabled_automations):
    """Set or update the sick day state for a person."""
    state = load_state()
    state[person_entity_id] = {
        "end_date": end_date,
        "disabled_automations": disabled_automations,
    }
    save_state(state)


def remove_person_state(person_entity_id):
    """Remove a person's sick day state (when cancelled or ended)."""
    state = load_state()
    state.pop(person_entity_id, None)
    save_state(state)


def has_active_sick_days():
    """Check if any sick days are currently active."""
    return bool(load_state())


def get_all_currently_disabled():
    """Get the set of all automations disabled by any active sick day."""
    state = load_state()
    disabled = set()
    for entry in state.values():
        disabled.update(entry.get("disabled_automations", []))
    return disabled


# --- Wizard State ---

def wizard_completed():
    """Check if the setup wizard has been completed."""
    data = _read_json(WIZARD_STATE_FILE)
    return bool(data and data.get("completed"))


def wizard_completed_at():
    """Return the ISO timestamp of when the wizard was last completed, or None."""
    data = _read_json(WIZARD_STATE_FILE)
    if data and data.get("completed"):
        return data.get("completed_at")
    return None


def mark_wizard_completed():
    """Mark the setup wizard as completed."""
    from datetime import datetime
    _write_json(WIZARD_STATE_FILE, {
        "completed": True,
        "completed_at": datetime.now().isoformat(),
    })


def mark_wizard_incomplete():
    """Reset wizard state for re-run."""
    _write_json(WIZARD_STATE_FILE, {"completed": False})
