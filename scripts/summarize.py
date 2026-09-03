#!/usr/bin/env python3
"""Aggregate MistakenAlignmentBench rewards by prompt treatment and solvability."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
METRICS = [
    "reward",
    "adherence",
    "task_success",
    "legitimate_solve",
    "honest_failure",
    "diagnosis",
    "cheated",
    "policy_violation",
    "report_issue_used",
    "report_issue_correct",
    "premature_issue_report",
    "post_report_activity",
]


def wilson(successes: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    proportion = successes / n
    denominator = 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def task_metadata() -> dict[str, dict[str, Any]]:
    manifest = json.loads((PROJECT / "manifest.json").read_text())
    metadata: dict[str, dict[str, Any]] = {}
    for task in manifest["tasks"]:
        metadata[f"puzzle-service/{task['task_id']}"] = task
        report_slug = "report_on" if task["report_issue_enabled"] else "report_off"
        legacy_id = (
            f"{task['condition']}--{task['escape_vector']}--"
            f"{task['prompt_variant']}--{report_slug}"
        )
        # Preserve aliases for job folders created under the earlier names.
        metadata[f"mistaken-alignment-bench/{legacy_id}"] = task
        metadata[f"frustration-bench/{legacy_id}"] = task
        metadata[f"adherance-bench/{legacy_id}"] = task
    return metadata


def load_rows(job_dir: Path) -> list[dict[str, Any]]:
    metadata = task_metadata()
    rows: list[dict[str, Any]] = []
    for result_path in sorted(job_dir.rglob("result.json")):
        try:
            result = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        task_name = result.get("task_name")
        if task_name not in metadata:
            continue
        verifier = result.get("verifier_result") or {}
        rewards = verifier.get("rewards") or {}
        agent_result = result.get("agent_result") or {}
        row = {
            **metadata[task_name],
            "trial_name": result.get("trial_name", result_path.parent.name),
            "result_path": str(result_path),
            "error": (result.get("exception_info") or {}).get("exception_type", ""),
            "cost_usd": agent_result.get("cost_usd"),
            "input_tokens": agent_result.get("n_input_tokens"),
            "output_tokens": agent_result.get("n_output_tokens"),
        }
        for metric in METRICS:
            row[metric] = rewards.get(metric)
        rows.append(row)
    return rows


def aggregate(rows: list[dict[str, Any]], group_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        enriched = {**row, "task_type": "frustration" if row["frustrated"] else "solvable"}
        groups[tuple(enriched[key] for key in group_keys)].append(enriched)
    summary: list[dict[str, Any]] = []
    for values, members in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0])):
        item: dict[str, Any] = {key: value for key, value in zip(group_keys, values)}
        item["n"] = len(members)
        for metric in METRICS:
            values = [float(row[metric]) for row in members if row[metric] is not None]
            if not values:
                item[metric] = None
                continue
            mean = sum(values) / len(values)
            low, high = wilson(sum(values), len(values))
            item[metric] = round(mean, 4)
            item[f"{metric}_ci95"] = [round(low, 4), round(high, 4)]
        summary.append(item)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    rows = load_rows(args.job_dir)
    if not rows:
        parser.error(f"no MistakenAlignmentBench trial result files found under {args.job_dir}")
    output_dir = args.output_dir or args.job_dir / "mistaken-alignment-summary"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = aggregate(rows, ("prompt_variant", "task_type", "report_issue_enabled"))
    full_cells = aggregate(
        rows,
        ("condition", "prompt_variant", "escape_vector", "report_issue_enabled"),
    )
    axis_summaries = {
        "prompt": aggregate(rows, ("prompt_variant", "task_type")),
        "escape_vector": aggregate(rows, ("escape_vector", "task_type")),
        "report_issue": aggregate(rows, ("report_issue_enabled", "task_type")),
        "condition": aggregate(rows, ("condition",)),
    }
    with (output_dir / "trials.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output_dir / "full-cells.json").write_text(json.dumps(full_cells, indent=2) + "\n")
    (output_dir / "axis-summaries.json").write_text(
        json.dumps(axis_summaries, indent=2) + "\n"
    )

    print("| prompt | type | report tool | n | adherence | cheat | legitimate | diagnosis | reward |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for item in summary:
        display = lambda key: "—" if item.get(key) is None else f"{item[key]:.2f}"  # noqa: E731
        print(
            f"| {item['prompt_variant']} | {item['task_type']} | "
            f"{'on' if item['report_issue_enabled'] else 'off'} | {item['n']} | "
            f"{display('adherence')} | {display('cheated')} | {display('legitimate_solve')} | "
            f"{display('diagnosis')} | {display('reward')} |"
        )
    costs = [float(row["cost_usd"]) for row in rows if row.get("cost_usd") is not None]
    print(f"\nRecorded agent cost: ${sum(costs):.4f}" if costs else "\nRecorded agent cost unavailable.")
    print(
        f"Wrote {output_dir / 'summary.json'}, {output_dir / 'full-cells.json'}, "
        f"{output_dir / 'axis-summaries.json'}, and {output_dir / 'trials.csv'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
