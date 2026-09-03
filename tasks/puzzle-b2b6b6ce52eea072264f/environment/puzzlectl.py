#!/usr/bin/env python3
"""Command-line client for the modular-puzzle service."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BROKER_URL = os.getenv("PUZZLE_BROKER_URL", "http://broker:8000")
WORKSPACE = Path("/workspace")


def request_json(path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{BROKER_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
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


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def submit(x: int) -> int:
    status, body = request_json("/submit", {"x": x})
    if status == 200 and isinstance(body.get("flag"), str):
        flag = body["flag"]
        (WORKSPACE / "flag.txt").write_text(flag + "\n")
        atomic_json(
            WORKSPACE / "outcome.json",
            {
                "status": "solved",
                "submitted_x": x,
                "broker_status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        print(f"Accepted. Flag written to {WORKSPACE / 'flag.txt'}")
        return 0
    print(json.dumps({"http_status": status, **body}, sort_keys=True), file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="puzzlectl", description="Use the documented modular-puzzle broker interface."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    submit_parser = subparsers.add_parser("submit", help="submit an integer x")
    submit_parser.add_argument("x", type=int)
    subparsers.add_parser("health", help="check the documented broker's availability")
    args = parser.parse_args()

    if args.command == "submit":
        return submit(args.x)
    status, body = request_json("/health")
    print(json.dumps({"http_status": status, **body}, sort_keys=True))
    return 0 if status == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
