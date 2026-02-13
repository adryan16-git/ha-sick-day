"""Home Assistant REST API wrapper using urllib (no external dependencies)."""

import json
import logging
import time
import urllib.request
import urllib.error

from sick_day_helper.constants import SUPERVISOR_URL, SUPERVISOR_TOKEN

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubles each retry


def _request(method, path, data=None):
    """Make an authenticated request to the HA API with retry logic."""
    url = f"{SUPERVISOR_URL}{path}"
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read().decode()
                if resp_body:
                    return json.loads(resp_body)
                return None
        except urllib.error.HTTPError as e:
            last_error = e
            resp_body = e.read().decode() if e.fp else ""
            logger.warning(
                "HA API %s %s returned %s (attempt %d/%d): %s",
                method, path, e.code, attempt + 1, MAX_RETRIES, resp_body,
            )
        except (urllib.error.URLError, OSError) as e:
            last_error = e
            logger.warning(
                "HA API %s %s failed (attempt %d/%d): %s",
                method, path, attempt + 1, MAX_RETRIES, e,
            )

        if attempt < MAX_RETRIES - 1:
            sleep_time = RETRY_BACKOFF * (2 ** attempt)
            time.sleep(sleep_time)

    raise last_error


def get_state(entity_id):
    """Get the full state object for an entity."""
    return _request("GET", f"/states/{entity_id}")


def get_state_value(entity_id):
    """Get just the state value string for an entity."""
    result = get_state(entity_id)
    return result.get("state") if result else None


def set_state(entity_id, state, attributes=None):
    """Set the state of an entity."""
    data = {"state": state}
    if attributes:
        data["attributes"] = attributes
    return _request("POST", f"/states/{entity_id}", data)


def get_states():
    """Get all entity states."""
    return _request("GET", "/states")


def call_service(domain, service, data=None):
    """Call a Home Assistant service."""
    return _request("POST", f"/services/{domain}/{service}", data or {})


def turn_on(entity_id):
    """Turn on an entity (automation, input_boolean, etc.)."""
    domain = entity_id.split(".")[0]
    return call_service(domain, "turn_on", {"entity_id": entity_id})


def turn_off(entity_id):
    """Turn off an entity."""
    domain = entity_id.split(".")[0]
    return call_service(domain, "turn_off", {"entity_id": entity_id})


def set_input_select_options(entity_id, options):
    """Set the options for an input_select entity."""
    return call_service("input_select", "set_options", {
        "entity_id": entity_id,
        "options": options,
    })


def select_option(entity_id, option):
    """Select an option on an input_select entity."""
    return call_service("input_select", "select_option", {
        "entity_id": entity_id,
        "option": option,
    })


def send_persistent_notification(message, title=None, notification_id=None):
    """Send a persistent notification in HA."""
    data = {"message": message}
    if title:
        data["title"] = title
    if notification_id:
        data["notification_id"] = notification_id
    return call_service("persistent_notification", "create", data)


def dismiss_persistent_notification(notification_id):
    """Dismiss a persistent notification."""
    return call_service("persistent_notification", "dismiss", {
        "notification_id": notification_id,
    })


def fire_event(event_type, event_data=None):
    """Fire a Home Assistant event."""
    return _request("POST", f"/events/{event_type}", event_data or {})


def render_template(template_str):
    """Render a Jinja2 template via HA's API. Returns the rendered string."""
    url = f"{SUPERVISOR_URL}/template"
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps({"template": template_str}).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode()


def get_automation_config(automation_id):
    """Get automation config by its config ID. Returns dict or None."""
    try:
        return _request("GET", f"/config/automation/config/{automation_id}")
    except Exception:
        logger.debug("Could not fetch automation config for %s", automation_id)
        return None
