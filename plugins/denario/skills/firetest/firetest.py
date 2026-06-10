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


def _unshadow(pkg: str) -> None:
    """Stop a sibling source checkout from shadowing the installed `pkg`.

    Run from a dir that contains a `cmbagent_lg/`/`denario/` *repo checkout*
    (e.g. ~/GitHub, where Claude Code's Bash runs), cwd lands on sys.path and
    Python imports that repo root as an empty namespace package — the real
    package's symbols (PlanContext, max_output_tokens_dict, …) go missing. Drop
    cwd and any sys.path entry whose immediate `pkg` child lacks an __init__.py.
    (Mirrors the MCP servers' own guard so the firetest imports what they do.)
    """
    drop = set()
    for p in list(sys.path):
        if p in ("", "."):
            drop.add(p)
            continue
        cand = os.path.join(p, pkg)
        if os.path.isdir(cand) and not os.path.isfile(os.path.join(cand, "__init__.py")):
            drop.add(p)
    if drop:
        sys.path[:] = [p for p in sys.path if p not in drop]


def _is_local(name: str) -> bool:
    n = name.lower()
    return "/" in name or n.startswith(_LOCAL_PREFIXES)


def _walk(node, path=""):
    """Yield (model_name, dotted_path, has_temperature) for each `model` spec.

    `has_temperature` matters because denario.llm.llm_parser reads
    `llm['temperature']` with no default — a spec missing the key raises
    `KeyError: 'temperature'` the moment its stage starts.
    """
    if isinstance(node, dict):
        if isinstance(node.get("model"), str):
            yield node["model"], path or "(root)", ("temperature" in node)
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

    _unshadow("cmbagent_lg")
    _unshadow("denario")
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

    # unique model -> list of (dotted usage path, has_temperature)
    usage: dict[str, list[tuple[str, bool]]] = {}
    for name, path, has_temp in _walk(params):
        usage.setdefault(name, []).append((path, has_temp))
    if not usage:
        print(f"No `model:` entries found in {args.params}.")
        return 0

    print(f"Firetest: {len(usage)} unique model(s) across "
          f"{sum(len(v) for v in usage.values())} role(s) in {args.params}\n")

    rows, ok_all = [], True
    for name in sorted(usage):
        uses = usage[name]
        local = _is_local(name)
        provider = "local" if local else _provider(name)
        notes = []

        in_reg = name in REGISTRY
        reg = "ok" if in_reg else "MISSING"

        # temperature: llm_parser does llm['temperature'] with no default,
        # so any role omitting it KeyErrors at stage setup.
        no_temp = [p for p, ht in uses if not ht]
        temp = "ok" if not no_temp else f"MISS x{len(no_temp)}"
        if no_temp:
            notes.append("no `temperature:` on -> " + ", ".join(sorted(no_temp)))

        if local:
            key = "n/a"
        else:
            key_env = _KEY_FOR.get(provider, "?")
            key = "ok" if os.environ.get(key_env) else f"NO {key_env}"

        if args.offline or local or key.startswith("NO") or not in_reg:
            live = "skip" if (args.offline or local) else "-"
            if local:
                notes.append("local endpoint — start its *_BASE_URL server to test")
        else:
            passed, detail = _live_ping(name, args.timeout)
            live = "ok" if passed else "FAIL"
            if not passed:
                notes.append(detail)

        failed = (not in_reg) or bool(no_temp) or key.startswith("NO") or live == "FAIL"
        ok_all = ok_all and not failed
        rows.append((name, provider, reg, temp, key, live, len(uses), failed, notes))

    w = max(len(r[0]) for r in rows)
    head = (f"{'MODEL':<{w}}  {'PROVIDER':<9} {'REG':<8} {'TEMP':<8} "
            f"{'KEY':<18} {'LIVE':<5} {'USES':<4}")
    print(head)
    print("-" * len(head))
    for name, provider, reg, temp, key, live, n_uses, failed, notes in rows:
        flag = "  <-- FIX" if failed else ""
        print(f"{name:<{w}}  {provider:<9} {reg:<8} {temp:<8} "
              f"{key:<18} {live:<5} {n_uses:<4}{flag}")
        for note in notes:
            print(f"{'':<{w}}  -> {note}")

    print()
    if ok_all:
        print("PASS - all models registered, keyed, temperature-set, and "
              "(where tested) reachable.")
        return 0
    print("FAIL - fix the rows marked <-- FIX before running the pipeline:")
    print("  REG MISSING -> add the model to denario/llm.py max_output_tokens_dict, "
          "or use a registered name.")
    print("  TEMP MISS   -> add `temperature: <float>` to that role; llm_parser "
          "requires it (it reads llm['temperature'] with no default).")
    print("  NO <KEY>    -> export that API key in the MCP server's environment.")
    print("  LIVE FAIL   -> the key/model pair was rejected; check the detail line above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
