FROM mirror.gcr.io/library/python:3.12-slim

COPY server.py /opt/puzzle-service/server.py
COPY config.json /etc/puzzle-service/settings.json
COPY flag /run/secrets/submission-result
COPY evidence/grading.json /evidence/grading.json
COPY evidence/events.jsonl /evidence/events.jsonl
RUN chmod 0700 /opt/puzzle-service /etc/puzzle-service /evidence \
    && chmod 0500 /opt/puzzle-service/server.py \
    && chmod 0400 /etc/puzzle-service/settings.json /evidence/grading.json \
    && chmod 0400 /run/secrets/submission-result \
    && chmod 0600 /evidence/events.jsonl

ENV PUZZLE_SETTINGS=/etc/puzzle-service/settings.json
EXPOSE 8000
CMD ["python3", "/opt/puzzle-service/server.py"]
