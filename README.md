# MistakenAlignmentBench

MistakenAlignmentBench is a Harbor benchmark for measuring what agents do when
the intended path through a task is broken or impossible. It varies prompt
language, failure mode, unintended flag exposure, and access to a terminal
`report_issue` tool, with matched solvable controls.

[Read the blog post](https://c.mov/mistaken-alignment) · [Explore the benchmark results](https://mab.c.mov)

## Quick start

Install [uv](https://docs.astral.sh/uv/) and Docker, then run:

```bash
uv sync
uv run python -m mistaken_alignment_bench.generate
uv run pytest
```

## Run the benchmark

Preview a four-task smoke test:

```bash
uv run python scripts/run_matrix.py --smoke
```

Add `--execute` to launch it. Use `-N` for repetitions, `--concurrency` for
parallelism, and `--environment daytona` for Daytona. Run the command with
`--help` to see all model, prompt, condition, and cost controls.

Harbor writes in-progress and completed runs to `jobs/`.

## Analyze a run

```bash
uv run python scripts/summarize.py jobs/<job-name>
```

The benchmark sources live in `mistaken_alignment_bench/`. Regenerate `tasks/`
after changing the matrix, prompts, or shared environment files.
