#!/usr/bin/with-contenv bashio

# Log startup
bashio::log.info "Starting Sick Day Helper add-on..."

# Read options from config
LOG_LEVEL=$(bashio::config 'LOG_LEVEL')
bashio::log.info "Log level set to: $LOG_LEVEL"
ENABLE_HEARTBEAT=$(bashio::config 'enable_heartbeat')
bashio::log.info "Heartbeat enabled: $ENABLE_HEARTBEAT"

# Hand off to Python service
exec python3 /sick_day_helper/main.py
