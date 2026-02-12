"""Copies the HA package YAML to /config/packages/ if needed."""

import filecmp
import logging
import os
import shutil

from sick_day_helper.constants import PACKAGE_SOURCE, PACKAGE_DEST, PACKAGE_DEST_DIR

logger = logging.getLogger(__name__)


def install_package():
    """Copy the package YAML to HA's packages directory.

    Returns True if the file was copied (new or updated), False if already up to date.
    """
    os.makedirs(PACKAGE_DEST_DIR, exist_ok=True)

    if os.path.isfile(PACKAGE_DEST) and filecmp.cmp(PACKAGE_SOURCE, PACKAGE_DEST, shallow=False):
        logger.debug("Package YAML already up to date")
        return False

    shutil.copy2(PACKAGE_SOURCE, PACKAGE_DEST)
    logger.info("Installed package YAML to %s", PACKAGE_DEST)
    return True
