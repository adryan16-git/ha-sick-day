"""Ingress HTTP server for the Sick Day Helper setup wizard."""

import json
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from sick_day_helper import ha_api, config_manager
from sick_day_helper.discovery import get_discovery_summary
from sick_day_helper.constants import (
    INGRESS_PORT,
    WEB_UI_DIR,
    ENTITY_PERSON_SELECT,
    NOTIFICATION_ONBOARDING,
)

logger = logging.getLogger(__name__)

MIME_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}


class WizardHandler(BaseHTTPRequestHandler):
    """Handles wizard API requests and static file serving."""

    def log_message(self, format, *args):
        logger.debug("HTTP %s", format % args)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status, message):
        self._send_json({"error": message}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_GET(self):
        # Strip query string
        path = self.path.split("?")[0]

        # API routes
        if path == "/api/status":
            return self._handle_status()
        if path == "/api/discovery":
            return self._handle_discovery()
        if path == "/api/mapping":
            return self._handle_get_mapping()

        # Static files
        self._serve_static(path)

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/mapping":
            return self._handle_save_mapping()
        if path == "/api/wizard/complete":
            return self._handle_wizard_complete()
        if path == "/api/wizard/reset":
            return self._handle_wizard_reset()

        self._send_error_json(404, "Not found")

    def _handle_status(self):
        self._send_json({
            "wizard_completed": config_manager.wizard_completed(),
            "mapping_exists": config_manager.mapping_exists(),
            "has_active_sick_days": config_manager.has_active_sick_days(),
            "mapping_count": len(config_manager.load_mapping()),
        })

    def _handle_discovery(self):
        try:
            summary = get_discovery_summary()
            self._send_json(summary)
        except Exception as e:
            logger.exception("Discovery failed")
            self._send_error_json(500, str(e))

    def _handle_get_mapping(self):
        self._send_json(config_manager.load_mapping())

    def _handle_save_mapping(self):
        try:
            mapping = self._read_body()
            config_manager.save_mapping(mapping)
            self._send_json({"ok": True})
        except Exception as e:
            logger.exception("Failed to save mapping")
            self._send_error_json(500, str(e))

    def _handle_wizard_complete(self):
        try:
            body = self._read_body()
            mapping = body.get("mapping", {})

            # Save mapping
            config_manager.save_mapping(mapping)

            # Mark wizard done
            config_manager.mark_wizard_completed()

            # Update person dropdown
            people_names = []
            for person_id in mapping:
                try:
                    state = ha_api.get_state(person_id)
                    name = state.get("attributes", {}).get("friendly_name", person_id) if state else person_id
                except Exception:
                    name = person_id
                people_names.append(name)

            if people_names:
                try:
                    ha_api.set_input_select_options(ENTITY_PERSON_SELECT, people_names)
                except Exception:
                    logger.debug("Could not update person dropdown (entity may not exist yet)")

            # Dismiss onboarding notification
            try:
                ha_api.dismiss_persistent_notification(NOTIFICATION_ONBOARDING)
            except Exception:
                pass

            self._send_json({"ok": True})
        except Exception as e:
            logger.exception("Failed to complete wizard")
            self._send_error_json(500, str(e))

    def _handle_wizard_reset(self):
        try:
            config_manager.mark_wizard_incomplete()
            self._send_json({"ok": True})
        except Exception as e:
            logger.exception("Failed to reset wizard")
            self._send_error_json(500, str(e))

    def _serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"

        file_path = os.path.join(WEB_UI_DIR, path.lstrip("/"))

        # Prevent directory traversal
        file_path = os.path.realpath(file_path)
        if not file_path.startswith(os.path.realpath(WEB_UI_DIR)):
            self.send_response(403)
            self.end_headers()
            return

        if not os.path.isfile(file_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        ext = os.path.splitext(file_path)[1]
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        with open(file_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def start_server():
    """Start the ingress web server in a daemon thread."""
    server = HTTPServer(("0.0.0.0", INGRESS_PORT), WizardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Ingress web server started on port %d", INGRESS_PORT)
    return server
