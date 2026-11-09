"""Reproducibility instrumentation plugin.

Loaded automatically by `plugins.hooks.discover_and_load()`. It records, per agent
run, the metrics the technical report reports in Table 4: total tokens
(input + output), the number of LLM requests, the number of tool calls and wall
clock time. Nothing here changes agent behaviour.

The numbers are accumulated from `llmcore.STATS`, which `llmcore._record_usage`
refreshes after every LLM response, plus the `tool_before` hook.

Output: `experiment_metrics.json` in the agent's working directory.
"""
import json
import os
import time

from plugins.hooks import register, trigger  # noqa: F401  (trigger kept for symmetry)
import llmcore

_T0 = time.time()
_TOKENS = {"input": 0, "output": 0, "cached": 0}
_REQUESTS = 0
_TOOL_CALLS = 0
_TOOL_NAME_COUNTS = {}
_SKIP_TOOLS = {"no_tool"}


@register("llm_after")
def _on_llm_after(ctx):
    global _REQUESTS
    _REQUESTS += 1
    stats = llmcore.STATS
    _TOKENS["input"] += int(stats.get("inp") or 0)
    _TOKENS["output"] += int(stats.get("out") or 0)
    _TOKENS["cached"] += int(stats.get("cached") or 0)


@register("tool_before")
def _on_tool_before(ctx):
    global _TOOL_CALLS
    name = ctx.get("tool_name") or ""
    if name in _SKIP_TOOLS:
        return
    _TOOL_CALLS += 1
    _TOOL_NAME_COUNTS[name] = _TOOL_NAME_COUNTS.get(name, 0) + 1


@register("agent_after")
def _on_agent_after(ctx):
    data = {
        "wall_time_s": round(time.time() - _T0, 1),
        "requests": _REQUESTS,
        "total_tokens": _TOKENS["input"] + _TOKENS["output"],
        "input_tokens": _TOKENS["input"],
        "output_tokens": _TOKENS["output"],
        "cached_input_tokens": _TOKENS["cached"],
        "tool_calls": _TOOL_CALLS,
        "tool_call_breakdown": dict(sorted(_TOOL_NAME_COUNTS.items())),
    }
    try:
        with open("experiment_metrics.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
