#!/usr/bin/env python3
"""Materialise one isolated trial workspace, run one GA task in it, grade it.

Usage:
    python experiments/run_trial.py teb_13_sql_copilot_query_generation --trial 1

Each trial gets a fresh copy of the upstream code (so memory/, temp/ and
model logs start from the pristine repo state), the task's input assets in the
workspace root exactly as the task prompt assumes, the metrics plugin, and a
mykey.py pointing at DeepSeek.

Results land in experiments/runs/<task_id>/trial_<n>/ (outside the trial
workspace) as metrics.json + grader.json, while the raw agent transcript and
produced files stay inside the trial workspace.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_SRC = ROOT / "genericagent"
DATASET = ROOT / "ga-eval" / "datasets" / "tool_efficiency_benchmark"
TRIALS = ROOT / "experiments" / "trials"
RUNS = ROOT / "experiments" / "runs"
PLUGIN = Path(__file__).resolve().parent / "metrics_recorder.py"
KEYFILE = ROOT / ".deepseek_key"

# heavy or irrelevant for a trial: demo media, paper PDFs, the outer venv/git
IGNORE = shutil.ignore_patterns(
    ".venv", ".git", "__pycache__", "*.pyc", "demo", "images", "*.pdf",
    "L4_raw_sessions", "stdout.log", "stderr.log", "model_responses", "_stop",
)


def build_key_module(dst: Path) -> None:
    key = KEYFILE.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    if not key:
        raise SystemExit(f"empty key file: {KEYFILE}")
    dst.write_text(
        "native_oai_config = {\n"
        "    'apibase': 'https://api.deepseek.com/v1',\n"
        f"    'apikey': {key!r},\n"
        "    'model': 'deepseek-chat',\n"
        "    'name': 'deepseek-chat',\n"
        "    'max_tokens': 8192,\n"
        "    'read_timeout': 600,\n"
        "    'max_retries': 3,\n"
        "}\n",
        encoding="utf-8",
    )


def prepare_workspace(task: dict, trial_dir: Path, condition: str = "baseline") -> None:
    if trial_dir.exists():
        shutil.rmtree(trial_dir)
    shutil.copytree(CODE_SRC, trial_dir, ignore=IGNORE)
    # GA's agent workspace is <repo>/temp (see get_global_memory), so the task
    # assets have to live there for the prompt's "当前工作区" to be true.
    work = trial_dir / "temp"
    work.mkdir(exist_ok=True)
    for rel in task.get("assets") or []:
        src = DATASET / rel
        if not src.is_file():
            raise SystemExit(f"missing asset: {src}")
        shutil.copy2(src, work / src.name)
    shutil.copy2(PLUGIN, trial_dir / "plugins" / "metrics_recorder.py")
    (trial_dir / "memory").mkdir(exist_ok=True)
    # a non-baseline condition is one text patch on top of the upstream system prompt
    patch = ROOT / "experiments" / "patch" / f"{condition}_sysprompt.txt"
    if condition != "baseline" and patch.is_file():
        with (trial_dir / "assets" / "sys_prompt.txt").open("a", encoding="utf-8") as f:
            f.write("\n" + patch.read_text(encoding="utf-8"))
    build_key_module(trial_dir / "mykey.py")
    (trial_dir / "PROMPT.md").write_text(task["prompt"], encoding="utf-8")


def run_agent(trial_dir: Path, log_path: Path, timeout_s: int) -> int:
    venv_py = CODE_SRC / ".venv" / "bin" / "python"
    cmd = [str(venv_py), "agentmain.py", "--func", "PROMPT.md", "--no-user-tools", "--nobg"]
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["GA_LANG"] = "zh"
    started = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        try:
            proc = subprocess.run(
                cmd, cwd=trial_dir, env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=timeout_s,
            )
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 124
    log_path.with_suffix(".elapsed").write_text(f"{time.time() - started:.1f}\n", encoding="utf-8")
    return code


def grade(task: dict, trial_dir: Path) -> dict:
    grader = DATASET / task["grader"]
    py = CODE_SRC / ".venv" / "bin" / "python"
    proc = subprocess.run(
        [str(py), str(grader), "--workspace", str(trial_dir / "temp")],
        capture_output=True, text=True, timeout=300,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"grader_error": proc.stdout[-2000:] + proc.stderr[-2000:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_id")
    ap.add_argument("--trial", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=2700)
    ap.add_argument("--condition", default="baseline")
    args = ap.parse_args()

    tasks = {t["task_id"]: t for t in (json.loads(l) for l in (DATASET / "tool_efficiency_tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
    if args.task_id not in tasks:
        raise SystemExit(f"unknown task {args.task_id}; have {sorted(tasks)}")
    task = tasks[args.task_id]

    trial_dir = TRIALS / f"{args.condition}_{args.task_id}_t{args.trial}"
    prepare_workspace(task, trial_dir, args.condition)

    run_dir = RUNS / args.condition / args.task_id / f"trial_{args.trial}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "agent.log"
    code = run_agent(trial_dir, log_path, args.timeout)

    metrics_path = trial_dir / "experiment_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    grader = grade(task, trial_dir)

    record = {
        "task_id": args.task_id,
        "condition": args.condition,
        "trial": args.trial,
        "model": "deepseek-chat",
        "exit_code": code,
        "metrics": metrics,
        "grader": grader,
        "trial_dir": str(trial_dir),
        "agent_log": str(log_path),
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (run_dir / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"task": args.task_id, "trial": args.trial, "success": grader.get("task_success"),
                      "score": grader.get("task_completion_score"), **metrics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
