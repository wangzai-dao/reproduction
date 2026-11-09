# Reproducing GenericAgent's long-horizon claims — FTEC5660

Reproducibility study of **GenericAgent** (*A Token-Efficient Self-Evolving LLM Agent via
Contextual Information Density Maximization*, [arXiv:2604.17091](https://arxiv.org/abs/2604.17091)),
targeting the long-horizon tool-use results in **Table 4** of the technical report.

**Student:** Wang Zihan · 1155267768 · FTEC5660

## What is in this repository

| File | What it is |
|---|---|
| `report.pdf` | The report (7 pages): target claim, setup, results vs Table 4, the modification, debug notes, limitations |
| `slides.pptx` | The 13-slide deck used for the recorded presentation |

## The claim that was reproduced

Table 4 of the technical report states that GenericAgent reaches **100% success on five
long-horizon tasks with 188,829 total tokens** — 35% of Claude Code's tokens at the same
success rate — using Claude Sonnet 4.6.

## What was done

* **Three of the five long-horizon tasks** were re-run (SQL copilot, experiment report,
  paper-to-slides), two trials each, using the authors' task definitions and **unmodified
  grading scripts** from
  [JinyiHan99/GA-Technical-Report](https://github.com/JinyiHan99/GA-Technical-Report).
* The agent code is upstream [lsdefine/GenericAgent@a9a36b4](https://github.com/lsdefine/GenericAgent)
  with **one** change: a 7-bullet "deliverable self-check" appended to `assets/sys_prompt.txt`.
* The language model was swapped to **DeepSeek-v4-pro** (permitted; it is the controlled
  variable), so results are not directly comparable to the paper's Claude numbers.
* Every trial starts from a fresh copy of the repository — no memory, no scratch files.
  Tokens, requests, tool calls and wall time are recorded by a 60-line plugin on the
  framework's own hooks.

## Results

| Condition | SQL task | Report task | Slides task | Overall |
|---|---:|---:|---:|---:|
| Baseline (upstream prompt) | 2/2 | 0/2 | 1/2 | **50% (3/6)** |
| + self-check policy | 2/2 | 0/2 | 2/2 | **67% (4/6)** |

The paper reports 100% on five tasks with 188,829 tokens. Under the same strict graders this
reproduction reaches 50% / 67% — the gap moves with the backbone (a smaller model scored
17% / 50%), so "100%" is a property of agent + model + grader, not of the agent alone.

**Failure analysis.** Both surviving failure families sit in the packaging step, not in
reasoning:

1. one run produced a valid deck but saved it under the wrong file name, so the grader found
   no artefact and scored 0.0;
2. the report task's prompt says the chart CSV must "at least contain" six columns while the
   grader requires exactly those six, and the report's length limit is counted differently by
   the prompt and the grader.

## How to reproduce

1. `git clone https://github.com/lsdefine/GenericAgent` and check out commit `a9a36b4`.
2. Append `self-check` from the report's Section 5 to `assets/sys_prompt.txt` (that is the
   only code change; the report reproduces the exact text).
3. Clone the authors' evaluation repo
   `https://github.com/JinyiHan99/GA-Technical-Report` — the three task prompts and the
   graders live under `datasets/tool_efficiency_benchmark/`.
4. Point `mykey.py` at any OpenAI-compatible endpoint (this study used `deepseek-v4-pro`)
   and run `python agentmain.py --func PROMPT.md --no-user-tools --nobg`.
5. Grade with `python <grader>.py --workspace <agent workspace>`; the agent writes into
   `<repo>/temp/`, so grade that directory.

Twelve runs took about 48 minutes of agent time and 4.7 M tokens (≈US$1.60 at off-peak
list price).
