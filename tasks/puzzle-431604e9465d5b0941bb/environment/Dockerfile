FROM mirror.gcr.io/library/python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl jq iproute2 netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY puzzlectl.py /usr/local/bin/puzzlectl
COPY runtime-state.txt /build/runtime-state.txt
COPY AGENTS.md /build/AGENTS.md
RUN chmod 0555 /usr/local/bin/puzzlectl
RUN mkdir -p /var/log/puzzlectl && cp /build/runtime-state.txt /var/log/puzzlectl/client.log && chmod 0644 /var/log/puzzlectl/client.log
RUN mkdir -p /workspace && cp /build/AGENTS.md /workspace/AGENTS.md && chmod 0444 /workspace/AGENTS.md
RUN rm -rf /build

WORKDIR /workspace
ENV PUZZLE_BROKER_URL=http://broker:8000
