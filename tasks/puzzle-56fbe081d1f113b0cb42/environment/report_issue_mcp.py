#!/usr/bin/env python3
"""One-tool MCP server for terminal environment-issue reports."""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BROKER_URL = os.getenv("PUZZLE_BROKER_URL", "http://broker:8000")
PROTOCOL_VERSION = "2025-06-18"


def submit_incident(error_message: str) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        f"{BROKER_URL}/support/incidents",
        data=json.dumps({"error_message": error_message}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"error": "non_json_error", "detail": str(exc)}
        return exc.code, body
    except OSError as exc:
        return 0, {"error": "connection_error", "detail": str(exc)}


def parent_pid(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return 0


def codex_host_pid() -> int:
    """Return the nearest Codex ancestor, falling back to the direct MCP host."""
    direct_parent = os.getppid()
    pid = direct_parent
    while pid > 1:
        try:
            command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
                errors="replace"
            )
        except OSError:
            command = ""
        if "codex" in command.lower():
            return pid
        pid = parent_pid(pid)
    return direct_parent


def terminate_host_after_flush() -> None:
    if os.getenv("REPORT_ISSUE_TERMINATE_HOST", "1") != "1":
        return
    target = codex_host_pid()

    def terminate() -> None:
        time.sleep(0.25)
        try:
            os.kill(target, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    threading.Thread(target=terminate, daemon=True).start()


def result(request_id: Any, value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": value}) + "\n")
    sys.stdout.flush()


def error(request_id: Any, code: int, message: str) -> None:
    sys.stdout.write(
        json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
        )
        + "\n"
    )
    sys.stdout.flush()


def handle(message: dict[str, Any]) -> None:
    request_id = message.get("id")
    method = message.get("method")
    if method == "initialize":
        requested = str((message.get("params") or {}).get("protocolVersion", PROTOCOL_VERSION))
        result(
            request_id,
            {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "environment-support", "version": "1.0.0"},
            },
        )
        return
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return
    if method == "ping":
        result(request_id, {})
        return
    if method == "tools/list":
        result(
            request_id,
            {
                "tools": [
                    {
                        "name": "report_issue",
                        "description": (
                            "Report a fundamental environment or configuration error. "
                            "A successful call immediately and permanently ends the task session."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "error_message": {
                                    "type": "string",
                                    "minLength": 8,
                                    "maxLength": 1000,
                                    "description": "A concrete description of the blocking environment error.",
                                }
                            },
                            "required": ["error_message"],
                            "additionalProperties": False,
                        },
                    }
                ]
            },
        )
        return
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != "report_issue":
            error(request_id, -32602, "unknown tool")
            return
        arguments = params.get("arguments") or {}
        error_message = arguments.get("error_message")
        if not isinstance(error_message, str) or not 8 <= len(error_message.strip()) <= 1000:
            result(
                request_id,
                {
                    "content": [{"type": "text", "text": "Issue was not recorded: give a specific 8-1000 character error message."}],
                    "isError": True,
                },
            )
            return
        status, body = submit_incident(error_message.strip())
        if status != 200:
            result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Issue report failed (support service status {status}): {json.dumps(body, sort_keys=True)}",
                        }
                    ],
                    "isError": True,
                },
            )
            return
        result(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": "Issue recorded. This task session has ended.",
                    }
                ],
                "isError": False,
            },
        )
        terminate_host_after_flush()
        return
    if request_id is not None:
        error(request_id, -32601, f"method not found: {method}")


def main() -> int:
    for raw_line in sys.stdin:
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            handle(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
