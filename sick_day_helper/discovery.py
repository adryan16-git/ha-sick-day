"""Enhanced entity/area/trigger discovery for Sick Day Helper wizard."""

import json
import logging
import re

from sick_day_helper import ha_api

logger = logging.getLogger(__name__)


def _extract_name_tokens(entity_id):
    """Extract name tokens from an entity ID for fuzzy matching."""
    name_part = entity_id.split(".", 1)[1] if "." in entity_id else entity_id
    tokens = set(re.split(r"[_\s]+", name_part.lower()))
    parts = re.split(r"[_\s]+", name_part.lower())
    for i in range(len(parts) - 1):
        tokens.add(f"{parts[i]}_{parts[i + 1]}")
    return tokens


def discover_people():
    """Return list of person entities: [{entity_id, friendly_name}, ...]."""
    all_states = ha_api.get_states()
    people = []
    for s in all_states:
        if s["entity_id"].startswith("person."):
            people.append({
                "entity_id": s["entity_id"],
                "friendly_name": s.get("attributes", {}).get("friendly_name", s["entity_id"]),
            })
    return sorted(people, key=lambda p: p["entity_id"])


def discover_automations():
    """Return all automation entities with friendly names and config IDs."""
    all_states = ha_api.get_states()
    automations = []
    for s in all_states:
        if s["entity_id"].startswith("automation."):
            attrs = s.get("attributes", {})
            automations.append({
                "entity_id": s["entity_id"],
                "friendly_name": attrs.get("friendly_name", s["entity_id"]),
                "config_id": attrs.get("id", ""),
                "state": s.get("state", "unknown"),
            })
    return sorted(automations, key=lambda a: a["entity_id"])


def discover_areas():
    """Use HA template API to discover areas and their automation entities."""
    areas = []
    try:
        # Get all area IDs
        area_ids_raw = ha_api.render_template("{{ areas() | list | tojson }}")
        area_ids = json.loads(area_ids_raw)

        for area_id in area_ids:
            # Get area name
            name = ha_api.render_template(f"{{{{ area_name('{area_id}') }}}}")
            # Get entities in this area
            entities_raw = ha_api.render_template(
                f"{{{{ area_entities('{area_id}') | list | tojson }}}}"
            )
            entity_ids = json.loads(entities_raw)
            # Filter to automations only
            automation_ids = [e for e in entity_ids if e.startswith("automation.")]

            areas.append({
                "area_id": area_id,
                "name": name.strip(),
                "automation_ids": automation_ids,
            })
    except Exception:
        logger.warning("Could not discover areas via template API, continuing without area data")

    return sorted(areas, key=lambda a: a["name"])


def classify_automation(entity_id, config_id):
    """Inspect automation triggers to classify it.

    Returns {time_triggered: bool, day_filtered: bool, trigger_summary: str}.
    """
    result = {"time_triggered": False, "day_filtered": False, "trigger_summary": ""}

    if not config_id:
        return result

    config = ha_api.get_automation_config(config_id)
    if not config:
        return result

    triggers = config.get("trigger", config.get("triggers", []))
    if isinstance(triggers, dict):
        triggers = [triggers]

    conditions = config.get("condition", config.get("conditions", []))
    if isinstance(conditions, dict):
        conditions = [conditions]

    # Check triggers
    trigger_types = []
    for t in triggers:
        platform = t.get("platform", t.get("trigger", ""))
        trigger_types.append(platform)
        if platform in ("time", "time_pattern"):
            result["time_triggered"] = True

    # Check conditions for day filtering
    for c in conditions:
        if "weekday" in c:
            result["day_filtered"] = True
            break
        cond_type = c.get("condition", "")
        if cond_type == "template":
            template = c.get("value_template", "")
            if "weekday" in template.lower():
                result["day_filtered"] = True
                break

    if trigger_types:
        result["trigger_summary"] = ", ".join(trigger_types)

    return result


def suggest_mapping(people, automations):
    """Auto-suggest person-to-automation mapping based on name matching."""
    mapping = {}
    for person in people:
        person_id = person["entity_id"]
        person_tokens = _extract_name_tokens(person_id)
        match_tokens = {t for t in person_tokens if len(t) > 1}

        matched = []
        for auto in automations:
            auto_tokens = _extract_name_tokens(auto["entity_id"])
            if match_tokens & auto_tokens:
                matched.append(auto["entity_id"])

        mapping[person_id] = sorted(matched)
    return mapping


def get_discovery_summary():
    """Aggregate discovery data for the wizard welcome step."""
    people = discover_people()
    automations = discover_automations()
    areas = discover_areas()

    # Classify automations
    time_triggered_count = 0
    day_filtered_count = 0
    automation_details = {}
    for auto in automations:
        classification = classify_automation(auto["entity_id"], auto["config_id"])
        auto["classification"] = classification
        automation_details[auto["entity_id"]] = auto
        if classification["time_triggered"]:
            time_triggered_count += 1
        if classification["day_filtered"]:
            day_filtered_count += 1

    # Build area-to-automation mapping
    area_automation_ids = set()
    for area in areas:
        area_automation_ids.update(area["automation_ids"])

    unassigned_automations = [
        a["entity_id"] for a in automations
        if a["entity_id"] not in area_automation_ids
    ]

    suggested_mapping = suggest_mapping(people, automations)

    return {
        "people": people,
        "automations": automations,
        "areas": areas,
        "unassigned_automations": unassigned_automations,
        "suggested_mapping": suggested_mapping,
        "counts": {
            "people": len(people),
            "automations": len(automations),
            "areas": len(areas),
            "time_triggered": time_triggered_count,
            "day_filtered": day_filtered_count,
        },
    }
