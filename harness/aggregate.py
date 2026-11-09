#!/usr/bin/env python3
"""Aggregate every trial result into one table (CSV + markdown + JSON).

Scans experiments/runs/<condition>/<task>/trial_*/result.json and prints, per
condition and task, the mean of the Table-4 metrics: success, total tokens,
requests, tool calls and wall time. Also reports a "fresh token" variant
(total minus cached input) because agent frameworks bill cached prompt tokens
very differently, which matters when comparing with the paper's numbers.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments" / "runs"
OUT = ROOT / "experiments" / "aggregate"


def load() -> list[dict]:
    rows = []
    for p in sorted(RUNS.glob("*/*/trial_*/result.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        m = d.get("metrics") or {}
        g = d.get("grader") or {}
        rows.append({
            "condition": d["condition"],
            "task": d["task_id"],
            "trial": d["trial"],
            "success": bool(g.get("task_success")),
            "score": g.get("task_completion_score"),
            "total_tokens": m.get("total_tokens"),
            "cached_tokens": m.get("cached_input_tokens"),
            "fresh_tokens": (m.get("total_tokens") or 0) - (m.get("cached_input_tokens") or 0),
            "requests": m.get("requests"),
            "tool_calls": m.get("tool_calls"),
            "wall_time_s": m.get("wall_time_s"),
            "exit_code": d.get("exit_code"),
        })
    return rows


def fmt(x, nd=1):
    return "" if x is None else f"{x:.{nd}f}"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def main() -> int:
    rows = load()
    if not rows:
        print("no results yet")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "trials.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    summary = {}
    lines = ["| condition | task | n | success | total tok | fresh tok | requests | tool calls | time (s) |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for cond in sorted({r["condition"] for r in rows}):
        for task in sorted({r["task"] for r in rows if r["condition"] == cond}):
            sub = [r for r in rows if r["condition"] == cond and r["task"] == task]
            agg = {
                "n": len(sub),
                "success": sum(r["success"] for r in sub) / len(sub),
                "total_tokens": mean([r["total_tokens"] for r in sub]),
                "fresh_tokens": mean([r["fresh_tokens"] for r in sub]),
                "requests": mean([r["requests"] for r in sub]),
                "tool_calls": mean([r["tool_calls"] for r in sub]),
                "wall_time_s": mean([r["wall_time_s"] for r in sub]),
                "score": mean([r["score"] for r in sub]),
            }
            summary.setdefault(cond, {})[task] = agg
            lines.append(
                f"| {cond} | {task} | {agg['n']} | {agg['success']:.0%} | "
                f"{fmt(agg['total_tokens'],0)} | {fmt(agg['fresh_tokens'],0)} | "
                f"{fmt(agg['requests'])} | {fmt(agg['tool_calls'])} | {fmt(agg['wall_time_s'])} |"
            )

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
