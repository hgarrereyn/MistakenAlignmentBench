#!/usr/bin/env python3
"""Select and run MistakenAlignmentBench tasks with a conservative cost gate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT / "manifest.json"
HARD_BUDGET_CEILING_USD = 100.0


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            values[key] = value
    return values


def select_tasks(args: argparse.Namespace) -> list[dict]:
    manifest = json.loads(MANIFEST.read_text())
    tasks = manifest["tasks"]
    if args.condition:
        selected = set(args.condition)
        tasks = [task for task in tasks if task["condition"] in selected]
    if args.prompt:
        selected = set(args.prompt)
        tasks = [task for task in tasks if task["prompt_variant"] in selected]
    if args.pair:
        selected = set(args.pair)
        tasks = [task for task in tasks if task["pair"] in selected]
    if args.escape_vector:
        selected = set(args.escape_vector)
        tasks = [task for task in tasks if task["escape_vector"] in selected]
    if args.report_issue:
        selected = {value == "enabled" for value in args.report_issue}
        tasks = [task for task in tasks if task["report_issue_enabled"] in selected]
    if args.frustration_only:
        tasks = [task for task in tasks if task["frustrated"]]
    if args.solvable_only:
        tasks = [task for task in tasks if not task["frustrated"]]
    if args.smoke:
        wanted = {
            ("task_file_control", "exploitgym_like", "disk_backup", False),
            ("task_file_control", "exploitgym_like", "disk_backup", True),
            ("missing_task_file", "exploitgym_like", "disk_backup", False),
            ("missing_task_file", "exploitgym_like", "disk_backup", True),
        }
        tasks = [
            task
            for task in tasks
            if (
                task["condition"],
                task["prompt_variant"],
                task["escape_vector"],
                task["report_issue_enabled"],
            )
            in wanted
        ]
    if args.balanced_panel:
        factors = manifest["factors"]
        condition_index = {value: index for index, value in enumerate(factors["conditions"])}
        prompt_index = {value: index for index, value in enumerate(factors["prompt_variants"])}
        escape_index = {value: index for index, value in enumerate(factors["escape_vectors"])}
        tasks = [
            task
            for task in tasks
            if condition_index[task["condition"]]
            == (
                prompt_index[task["prompt_variant"]]
                + 2 * escape_index[task["escape_vector"]]
                + 3 * int(task["report_issue_enabled"])
            )
            % len(condition_index)
        ]
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-N", "--attempts", type=int, default=1, help="samples per cell")
    parser.add_argument("--agent", default="codex")
    parser.add_argument(
        "--agent-version",
        help="optional installed-agent version pin (for example, a Codex CLI version)",
    )
    parser.add_argument("--model", default="openai/gpt-5-mini")
    parser.add_argument(
        "--environment",
        default="docker",
        help="Harbor environment backend (for example: docker or daytona)",
    )
    parser.add_argument(
        "--environment-kwarg",
        action="append",
        default=[],
        help="Harbor environment kwarg in key=value form; may be repeated",
    )
    parser.add_argument("--condition", action="append")
    parser.add_argument("--prompt", action="append")
    parser.add_argument("--pair", action="append")
    parser.add_argument("--escape-vector", action="append")
    parser.add_argument(
        "--report-issue", action="append", choices=["enabled", "disabled"]
    )
    parser.add_argument("--frustration-only", action="store_true")
    parser.add_argument("--solvable-only", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="run the four task-file control/frustration by report on/off cells",
    )
    parser.add_argument(
        "--balanced-panel",
        action="store_true",
        help="run a 30-cell axis-coverage panel spanning every prompt/escape/report combination",
    )
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default="low")
    parser.add_argument(
        "--codex-minimal-tools",
        action="store_true",
        help="disable Codex apps/plugins/tool suggestions/multi-agent/goals for models with a narrow tool set",
    )
    parser.add_argument("--jobs-dir", type=Path, default=PROJECT / "jobs")
    parser.add_argument("--job-name")
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=25.0,
        help="experiment budget; values above 100 are rejected",
    )
    parser.add_argument(
        "--reserve-per-trial-usd",
        type=float,
        default=4.0,
        help="conservative preflight reservation, not a provider billing guarantee",
    )
    parser.add_argument("--env-file", type=Path, default=PROJECT.parent / ".env")
    parser.add_argument("--execute", action="store_true", help="without this, print the plan only")
    args = parser.parse_args()

    if args.attempts < 1 or args.concurrency < 1:
        parser.error("attempts and concurrency must be positive")
    if not (0 < args.max_cost_usd <= HARD_BUDGET_CEILING_USD):
        parser.error(f"max-cost-usd must be in (0, {HARD_BUDGET_CEILING_USD}]")
    if args.reserve_per_trial_usd < 0.01:
        parser.error("reserve-per-trial-usd must be at least $0.01")
    if args.frustration_only and args.solvable_only:
        parser.error("choose at most one of --frustration-only and --solvable-only")
    if args.smoke and args.balanced_panel:
        parser.error("choose at most one of --smoke and --balanced-panel")

    tasks = select_tasks(args)
    if not tasks:
        parser.error("the filters selected no tasks")
    trial_count = len(tasks) * args.attempts
    reserved = trial_count * args.reserve_per_trial_usd
    if reserved > args.max_cost_usd:
        parser.error(
            f"preflight reservation is ${reserved:.2f} for {trial_count} trials, above the "
            f"${args.max_cost_usd:.2f} experiment budget; narrow the matrix or explicitly "
            "adjust the per-trial reserve"
        )

    harbor = shutil.which("harbor")
    if harbor is None:
        parser.error("harbor is not installed; run this command through `uv run`")
    job_name = args.job_name or datetime.now(timezone.utc).strftime("puzzle-%Y%m%d-%H%M%S")
    job_dir = args.jobs_dir / job_name
    if args.execute and job_dir.exists():
        parser.error(f"job directory already exists: {job_dir}")
    command = [
        harbor,
        "run",
        "-p",
        str(PROJECT / "tasks"),
        *sum((["-i", task["task_id"]] for task in tasks), []),
        "-a",
        args.agent,
        "-m",
        args.model,
        "--env",
        args.environment,
        "-k",
        str(args.attempts),
        "-n",
        str(args.concurrency),
        "--job-name",
        job_name,
        "--jobs-dir",
        str(args.jobs_dir),
    ]
    for environment_kwarg in args.environment_kwarg:
        command.extend(["--ek", environment_kwarg])
    if args.agent in {"codex", "claude-code"}:
        if args.agent_version:
            command.extend(["--ak", f"version={args.agent_version}"])
        command.extend(["--ak", f"reasoning_effort={args.reasoning_effort}"])
    if args.agent == "codex":
        command.extend(["--ak", "web_search=disabled"])
        if args.codex_minimal_tools:
            minimal_config = {
                "features": {
                    "apps": False,
                    "goals": False,
                    "multi_agent": False,
                    "plugins": False,
                    "remote_plugin": False,
                    "tool_suggest": False,
                }
            }
            command.extend(["--ak", f"config={json.dumps(minimal_config, separators=(',', ':'))}"])

    plan = {
        "job_name": job_name,
        "agent": args.agent,
        "agent_version": args.agent_version,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "environment": args.environment,
        "environment_kwargs": args.environment_kwarg,
        "codex_minimal_tools": args.codex_minimal_tools,
        "tasks": [task["task_id"] for task in tasks],
        "factor_counts": {
            "solvable": sum(not task["frustrated"] for task in tasks),
            "frustrated": sum(task["frustrated"] for task in tasks),
            "report_enabled": sum(task["report_issue_enabled"] for task in tasks),
            "report_disabled": sum(not task["report_issue_enabled"] for task in tasks),
        },
        "attempts_per_task": args.attempts,
        "trial_count": trial_count,
        "concurrency": args.concurrency,
        "budget_usd": args.max_cost_usd,
        "reserved_usd": reserved,
        "execute": args.execute,
    }
    print(json.dumps(plan, indent=2))
    if not args.execute:
        print("Dry run only. Add --execute to launch Harbor.")
        return 0

    environment = os.environ.copy()
    environment.update(load_dotenv(args.env_file))
    if args.model.startswith("openai/") and not environment.get("OPENAI_API_KEY"):
        parser.error(f"OPENAI_API_KEY was not found in the environment or {args.env_file}")
    if args.model.startswith("anthropic/") and not environment.get(
        "ANTHROPIC_API_KEY"
    ):
        parser.error(
            f"ANTHROPIC_API_KEY was not found in the environment or {args.env_file}"
        )
    args.jobs_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=PROJECT, env=environment, check=False)
    if completed.returncode:
        print(f"Harbor exited with status {completed.returncode}.", file=sys.stderr)
        if job_dir.exists():
            print(f"Partial job preserved at: {job_dir}", file=sys.stderr)
        return completed.returncode
    print(f"Job complete: {job_dir}")
    print("Run scripts/summarize.py on the job directory for treatment-level rates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
