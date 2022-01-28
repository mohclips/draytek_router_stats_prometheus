FROM python:3-slim

LABEL author="mohclips"

RUN set -eux; \
    useradd -ms /bin/bash puser; \
    pip install prometheus_client pexpect ttp; \
    apt update; \
    apt-get install -y --no-install-recommends \
        telnet \
        && rm -rf /var/lib/apt/lists/* ; \
    echo "Done"

# run as non-root user - safety first!
USER puser
WORKDIR /home/puser

# copy code into image
COPY src/ /home/puser/

# fix for https://github.com/dmulyalin/ttp/issues/54
ENV TTPCACHEFOLDER=/tmp
ENV IP="192.168.0.1"
ENV USERNAME="admin"
ENV PASSWORD="password"

ENV SERVER_PORT=8081
ENV METRICS_PORT=8001

# where does telnet live?
ENV TELNET_CMD='/usr/bin/telnet' 
# timeout to telnet to router and grab stats
ENV SPAWN_TIMEOUT=5

EXPOSE 8081
EXPOSE 8001

# and run the code :)
ENTRYPOINT ["python3"]
CMD ["get_stats_om.py"]