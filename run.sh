#!/usr/bin/with-contenv bashio

# Log startup
bashio::log.info "Starting Sick Day Helper add-on..."

# Hand off to Python service
export PYTHONPATH=/
exec python3 /sick_day_helper/main.py
