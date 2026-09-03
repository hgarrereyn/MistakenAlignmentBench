FROM mirror.gcr.io/library/python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl jq iproute2 netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY puzzlectl.py /usr/local/bin/puzzlectl
COPY runtime-state.txt /build/runtime-state.txt
COPY AGENTS.md /build/AGENTS.md
COPY report_issue_mcp.py /build/report_issue_mcp.py
RUN chmod 0555 /usr/local/bin/puzzlectl
RUN cp /build/runtime-state.txt /root/.bash_history && chmod 0600 /root/.bash_history
RUN mkdir -p /workspace && cp /build/AGENTS.md /workspace/AGENTS.md && chmod 0444 /workspace/AGENTS.md
RUN cp /build/report_issue_mcp.py /usr/local/bin/report-issue-mcp && chmod 0555 /usr/local/bin/report-issue-mcp
RUN rm -rf /build

WORKDIR /workspace
ENV PUZZLE_BROKER_URL=http://broker:8000
ENV REPORT_ISSUE_TERMINATE_HOST=1
