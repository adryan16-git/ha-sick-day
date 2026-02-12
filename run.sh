#!/usr/bin/with-contenv bashio

# Log startup
bashio::log.info "Starting Sick Day Helper add-on..."

# Read options from config
LOG_LEVEL=$(bashio::config 'LOG_LEVEL')
bashio::log.info "Log level set to: $LOG_LEVEL"
ENABLE_HEARTBEAT=$(bashio::config 'enable_heartbeat')
bashio::log.info "Heartbeat enabled: $ENABLE_HEARTBEAT"

# Main service loop
while true; do
    # Placeholder: Add sick-day logic here
    # Example: Check HA states, send notifications, etc.
    bashio::log.debug "Sick Day Helper running..."
    bashio::log.info "Heartbeat at $(date)"
    sleep 60
done