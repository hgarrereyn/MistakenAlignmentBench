from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SERVER = PROJECT / "mistaken_alignment_bench/common/environment/report_issue_mcp.py"


class ReportHandler(BaseHTTPRequestHandler):
    message: str | None = None
    path_seen: str | None = None

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        type(self).path_seen = self.path
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        type(self).message = body["error_message"]
        response = json.dumps({"recorded": True, "session_ended": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def exchange(process: subprocess.Popen[str], message: dict) -> dict:
    assert process.stdin and process.stdout
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()
    return json.loads(process.stdout.readline())


def test_mcp_server_advertises_and_records_terminal_report() -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ReportHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    environment = os.environ.copy()
    environment["PUZZLE_BROKER_URL"] = f"http://127.0.0.1:{httpd.server_port}"
    environment["REPORT_ISSUE_TERMINATE_HOST"] = "0"
    process = subprocess.Popen(
        ["python3", str(SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        initialized = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
            },
        )
        assert initialized["result"]["capabilities"]["tools"] == {"listChanged": False}
        tools = exchange(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert [tool["name"] for tool in tools["result"]["tools"]] == ["report_issue"]
        called = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "report_issue",
                    "arguments": {"error_message": "The required task file is missing."},
                },
            },
        )
        assert called["result"]["isError"] is False
        assert ReportHandler.message == "The required task file is missing."
        assert ReportHandler.path_seen == "/support/incidents"
    finally:
        process.terminate()
        process.wait(timeout=5)
        httpd.shutdown()
        httpd.server_close()
