ARG BUILD_FROM
FROM $BUILD_FROM

# Install python3 and pip
RUN apk add --no-cache python3 py3-pip

# Copy run.sh and make it executable
COPY run.sh /run.sh
RUN chmod +x /run.sh

# Copy Python application, HA package, Lovelace card, and web UI
COPY sick_day_helper/ /sick_day_helper/
COPY packages/ /packages/
COPY lovelace/ /lovelace/
COPY web_ui/ /web_ui/

CMD ["/run.sh"]
