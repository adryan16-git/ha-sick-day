"""First-run onboarding: send notification pointing to the setup wizard."""

import logging

from sick_day_helper import ha_api
from sick_day_helper.constants import NOTIFICATION_ONBOARDING

logger = logging.getLogger(__name__)


def run_onboarding():
    """Send a notification directing the user to the ingress wizard.

    Returns True if notification sent, False on failure.
    """
    logger.info("No mapping found — sending wizard notification")

    try:
        ha_api.send_persistent_notification(
            title="Sick Day Helper — Setup Required",
            message=(
                "Open **Sick Day Helper** from the sidebar to run the setup wizard.\n\n"
                "The wizard will help you map people to automations that should be "
                "disabled on sick days."
            ),
            notification_id=NOTIFICATION_ONBOARDING,
        )
        return True
    except Exception:
        logger.exception("Failed to send onboarding notification")
        return False
