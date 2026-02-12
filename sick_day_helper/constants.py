"""Constants for Sick Day Helper."""

import os

# HA API
SUPERVISOR_URL = "http://supervisor/core/api"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

# File paths
DATA_DIR = "/config/.sick_day_helper"
MAPPING_FILE = os.path.join(DATA_DIR, "mapping.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
PACKAGE_SOURCE = "/packages/sick_day_helper.yaml"
PACKAGE_DEST_DIR = "/config/packages"
PACKAGE_DEST = os.path.join(PACKAGE_DEST_DIR, "sick_day_helper.yaml")

# Poll interval (seconds)
POLL_INTERVAL = 10

# Entity IDs
ENTITY_PERSON_SELECT = "input_select.sick_day_person"
ENTITY_DURATION_TYPE = "input_select.sick_day_duration_type"
ENTITY_NUM_DAYS = "input_number.sick_day_num_days"
ENTITY_END_DATE = "input_datetime.sick_day_end_date"
ENTITY_SUBMIT = "input_boolean.sick_day_submit"
ENTITY_CANCEL = "input_boolean.sick_day_cancel"
ENTITY_EXTEND = "input_boolean.sick_day_extend"
ENTITY_ACTIVE = "input_boolean.sick_day_active"
ENTITY_SETUP_COMPLETE = "input_boolean.sick_day_setup_complete"

# Duration type options
DURATION_NUM_DAYS = "Number of Days"
DURATION_UNTIL_DATE = "Until Date"

# Notification IDs
NOTIFICATION_EXPIRATION = "sick_day_expiration"
NOTIFICATION_ONBOARDING = "sick_day_onboarding"
NOTIFICATION_CONFIRMATION = "sick_day_confirmation"

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()
