#!/usr/bin/env python3
"""Firetest the models declared in a Denario params.yaml.

Pre-flight smoke test so a long pipeline run doesn't die minutes in on a bad
model name or a missing API key. For every `{ model: ... }` spec anywhere in
params.yaml it checks three layers, reusing Denario's OWN logic so the result
mirrors what the pipeline does:

  1. REGISTRY  - name is in `denario.llm.max_output_tokens_dict`; otherwise
                 `llm_parser` raises KeyError the moment a stage starts.
  2. KEY       - the provider inferred from the name (same `_provider` as
                 cmbagent_lg) has its API key in the environment.
  3. LIVE      - actually builds the chat model via `cmbagent_lg.llms.chat_model`
                 and sends a one-token ping (skippable with --offline).

Run it on the SAME interpreter/env the Denario MCP servers use (the
cmbagent_lg venv), so the keys and registry it sees match the real run:

    /Users/boris/pyvenvs/py312-cmbagent-lg/bin/python firetest.py path/to/params.yaml

Exit code 0 = every model passed every attempted layer; 1 = at least one failed.
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

# Local OpenAI-compatible endpoints (nemotron/qwen/kimi/minimax/gpt-oss/deepseek/
# gemma paths). These are in the registry but need their own *_BASE_URL server
# up; cmbagent_lg's chat_model doesn't route them, so we don't live-ping them.
_LOCAL_PREFIXES = ("nvidia", "nemotron", "qwen", "moonshotai", "minimax",
                   "openai/gpt-oss", "deepseek", "/rds/", "gemma")

_KEY_FOR = {"google": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY"}


def _is_local(name: str) -> bool:
    n = name.lower()
    return "/" in name or n.startswith(_LOCAL_PREFIXES)


def _walk(node, path=""):
    """Yield (model_name, dotted_path) for every dict that has a str `model`."""
    if isinstance(node, dict):
        if isinstance(node.get("model"), str):
            yield node["model"], path or "(root)"
        for k, v in node.items():
            child = f"{path}.{k}" if path else str(k)
            yield from _walk(v, child)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def _live_ping(model: str, timeout: float) -> tuple[bool, str]:
    """Build the chat model the way the pipeline does and send a tiny prompt."""
    from cmbagent_lg.llms import chat_model

    def _call():
        llm = chat_model(model)
        resp = llm.invoke("Reply with the single word: ok")
        text = getattr(resp, "content", resp)
        return True, (str(text).strip().replace("\n", " ")[:40] or "(empty)")

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_call).result(timeout=timeout)
    except Exception as e:  # noqa: BLE001 - smoke test, report any failure
        msg = str(e).splitlines()[0] if str(e) else type(e).__name__
        return False, f"{type(e).__name__}: {msg[:120]}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Firetest Denario params.yaml models.")
    ap.add_argument("params", nargs="?", default="params.yaml",
                    help="path to params.yaml (default: ./params.yaml)")
    ap.add_argument("--offline", action="store_true",
                    help="skip the live API ping; only check registry + keys")
    ap.add_argument("--timeout", type=float, default=30.0,
                    help="per-model live-ping timeout in seconds (default 30)")
    args = ap.parse_args()

    try:
        import yaml
        from denario.llm import max_output_tokens_dict as REGISTRY
        from cmbagent_lg.llms import _provider
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: import failed ({e}). Run this on the cmbagent_lg venv "
              f"(the one the Denario MCP servers use).", file=sys.stderr)
        return 2

    if not os.path.isfile(args.params):
        print(f"ERROR: no such file: {args.params}", file=sys.stderr)
        return 2

    with open(args.params) as f:
        params = yaml.safe_load(f)

    # unique model -> sorted list of dotted usage paths
    usage: dict[str, list[str]] = {}
    for name, path in _walk(params):
        usage.setdefault(name, []).append(path)
    if not usage:
        print(f"No `model:` entries found in {args.params}.")
        return 0

    print(f"Firetest: {len(usage)} unique model(s) across "
          f"{sum(len(v) for v in usage.values())} role(s) in {args.params}\n")

    rows, ok_all = [], True
    for name in sorted(usage):
        local = _is_local(name)
        provider = "local" if local else _provider(name)

        in_reg = name in REGISTRY
        reg = "ok" if in_reg else "MISSING"

        if local:
            key = "n/a"
        else:
            key_env = _KEY_FOR.get(provider, "?")
            key = "ok" if os.environ.get(key_env) else f"NO {key_env}"

        if args.offline or local or key.startswith("NO") or not in_reg:
            live = "skip" if (args.offline or local) else "-"
            note = "local endpoint — start its *_BASE_URL server to test" if local else ""
        else:
            passed, detail = _live_ping(name, args.timeout)
            live, note = ("ok", "") if passed else ("FAIL", detail)

        failed = (not in_reg) or key.startswith("NO") or live == "FAIL"
        ok_all = ok_all and not failed
        rows.append((name, provider, reg, key, live, len(usage[name]), note))

    w = max(len(r[0]) for r in rows)
    head = f"{'MODEL':<{w}}  {'PROVIDER':<9} {'REG':<8} {'KEY':<18} {'LIVE':<5} {'USES':<4}"
    print(head)
    print("-" * len(head))
    for name, provider, reg, key, live, uses, note in rows:
        flag = "" if (reg == "ok" and not key.startswith("NO") and live != "FAIL") else "  <-- FIX"
        print(f"{name:<{w}}  {provider:<9} {reg:<8} {key:<18} {live:<5} {uses:<4}{flag}")
        if note:
            print(f"{'':<{w}}  -> {note}")

    print()
    if ok_all:
        print("PASS - all models resolved, keyed, and (where tested) reachable.")
        return 0
    print("FAIL - fix the rows marked <-- FIX before running the pipeline:")
    print("  REG MISSING -> add the model to denario/llm.py max_output_tokens_dict, "
          "or use a registered name.")
    print("  NO <KEY>    -> export that API key in the MCP server's environment.")
    print("  LIVE FAIL   -> the key/model pair was rejected; check the detail line above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
