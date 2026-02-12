ARG BUILD_FROM
FROM $BUILD_FROM

# Install python3 and pip
RUN apk add --no-cache python3 py3-pip

# Copy run.sh and make it executable
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
