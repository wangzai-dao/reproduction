# Reproducing GenericAgent's long-horizon claims — FTEC5660

**Wang Zihan · 1155267768 · FTEC5660 Reproducibility Work**

Reproducibility study of **GenericAgent** (*A Token-Efficient Self-Evolving LLM Agent via
Contextual Information Density Maximization*, [arXiv:2604.17091](https://arxiv.org/abs/2604.17091)),
targeting the long-horizon tool-use result in **Table 4** of its technical report.

* **Report:** [`report.pdf`](report.pdf) — 7 pages
* **Presentation deck:** [`slides.pptx`](slides.pptx) — 13 slides

---

## 1. What we tried to reproduce

Table 4 claims that GenericAgent reaches **100% success on five long-horizon tasks with
188,829 total tokens** — 35% of Claude Code's tokens at the same success rate — on
Claude Sonnet 4.6.

We reproduced **three of the five tasks** (SQL copilot, experiment report, paper-to-slides)
using the authors' own task definitions and **unmodified graders**, and then applied **one**
change and measured its effect.

## 2. Repository contents

| Path | What it is |
|---|---|
| `report.pdf` | The report: target claim, setup, results vs Table 4, the change, debug notes, limitations |
| `slides.pptx` | 13-slide deck for the recorded presentation |
| `patches/selfcheck_sysprompt.txt` | **The one change** — this block is appended to `assets/sys_prompt.txt` |
| `harness/run_trial.py` | Runs one isolated trial: fresh repo copy → agent → grade → record |
| `harness/metrics_recorder.py` | Plugin that records tokens, requests, tool calls and wall time via the framework's hooks |
| `harness/aggregate.py` | `results/trials.csv` → per-task means |
| `results/trials.csv` | All 12 trials, one row each (condition, model, task, success, score, tokens, requests, tool calls, wall time) |

## 3. Install

Requires Python 3.11 or 3.12 and an API key for any OpenAI-compatible endpoint.
Everything below is run from the repository root.

```bash
# the agent under test, pinned to the commit used in this study
git clone https://github.com/lsdefine/GenericAgent.git genericagent
git -C genericagent checkout a9a36b4

# its dependencies (core only; no UI extras are needed to run headless)
python3 -m venv genericagent/.venv
genericagent/.venv/bin/pip install --index-url https://pypi.org/simple \
    requests beautifulsoup4 bottle simple-websocket-server aiohttp

# the benchmark: task prompts, input assets and the authors' graders
git clone --depth 1 https://github.com/JinyiHan99/GA-Technical-Report.git ga-eval
```

Model configuration is one file at the repository root — the runner builds each trial's
`mykey.py` from it:

```bash
printf '%s\n' 'sk-your-key' > .deepseek_key      # never committed
export GA_MODEL=deepseek-v4-pro                   # default; any OpenAI-compatible model works
```

## 4. Run

```bash
# one trial, baseline condition (upstream system prompt)
python3 harness/run_trial.py teb_13_sql_copilot_query_generation --trial 1

# one trial, with the change applied (patches/selfcheck_sysprompt.txt)
python3 harness/run_trial.py teb_13_sql_copilot_query_generation --trial 1 --condition selfcheck

# all twelve runs, in the order used in the report
for c in baseline selfcheck; do
  for t in teb_13_sql_copilot_query_generation \
           teb_14_experiment_analysis_report_generation \
           teb_12_paper_ppt_generation; do
    for n in 1 2; do python3 harness/run_trial.py "$t" --trial "$n" --condition "$c"; done
  done
done

# aggregate the twelve per-trial records
python3 harness/aggregate.py
```

For each trial, `run_trial.py`

1. copies `genericagent/` into `experiments/trials/<condition>_<task>_t<n>/` — so memory,
   scratch files and logs start fresh, with no cross-trial state;
2. copies the task's input assets into that copy's `temp/`, which is the directory the agent
   treats as its workspace;
3. runs the agent headless (`agentmain.py --func PROMPT.md --no-user-tools --nobg`);
4. grades the workspace with the authors' unmodified script from `ga-eval/`;
5. writes `experiments/runs/<condition>/<task>/trial_<n>/result.json` with the metrics.

A full twelve-run sweep is about 48 minutes of agent time and 4.7 M tokens (≈US$1.60 at
off-peak list price for `deepseek-v4-pro`).

## 5. The change

`patches/selfcheck_sysprompt.txt` is appended to `assets/sys_prompt.txt`. It is prompt text
only — no code, no tool, no grader was modified:

* before finishing, the agent must open every artefact with the right library;
* count pages, characters and columns against the stated limits;
* check file names, encoding (UTF-8, no BOM) and header equality;
* confirm that whatever must be "last" really is last, and add no unrequested appendices.

It was written **after** inspecting the baseline failures, and the report says so explicitly.

## 6. Results

| Condition | SQL task | Report task | Slides task | Overall | Tokens per task |
|---|---:|---:|---:|---:|---:|
| Baseline (upstream prompt) | 2/2 | 0/2 | 1/2 | **50% (3/6)** | 0.23–1.52 M |
| + self-check | 2/2 | 0/2 | 2/2 | **67% (4/6)** | 0.43–1.50 M |

Paper, same table, Claude Sonnet 4.6: 100% · 188,829 tokens · 11.0 requests · 220.8 s.

Both surviving failures are packaging failures rather than reasoning failures:

1. one run produced a valid deck but saved it as `DAPO_paper_share.pptx` instead of
   `presentation.pptx`, so the grader found no artefact and scored 0.0;
2. the report task's prompt asks for a chart CSV that "at least contains" six columns while
   the grader requires exactly those six, and the 600–1200 character limit is counted
   differently by the prompt and the grader.

## 7. Notes

* The backbone is **DeepSeek-v4-pro**, not the paper's Claude Sonnet 4.6, so absolute numbers
  are cross-model and not directly comparable. A smaller DeepSeek model scored 17% / 50%,
  which is itself evidence that "100%" depends on the backbone.
* Token totals count each request's prompt + completion. 82–90% of prompt tokens are cache
  hits; the paper does not define its "accounted tokens" convention, so its 188,829 figure
  cannot be compared like-for-like.
* n = 2 trials per cell: the failure taxonomy is the claim, not the percentages.
* No secrets are committed; the model key is supplied through `mykey.py`, which is ignored.
