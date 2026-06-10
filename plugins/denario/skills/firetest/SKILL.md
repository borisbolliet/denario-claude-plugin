---
description: Pre-flight smoke test ("firetest") of every model declared in a Denario params.yaml — checks each model name is registered, its provider API key is present, and (live) that the key/model pair actually responds, before committing to a long pipeline run. Use right after writing/editing params.yaml and before denario_idea/methods/results.
when_to_use: User is about to run the Denario pipeline (or just wrote/edited a params.yaml) and wants to confirm the configured models will work — catch a bad/unregistered model name or a missing API key in seconds instead of failing minutes into denario_results. Also when a run just died with a KeyError on a model name or an auth/credit error.
argument-hint: "<project_dir or params.yaml> [--offline] [--timeout=30]"
allowed-tools: Read Glob Bash
---

# Firetest the models in params.yaml

A long Denario run can die minutes in on a single bad model name (`llm_parser`
raises `KeyError`), a missing `temperature`, or a missing API key. This skill
runs every `{ model: ... }` spec in a project's `params.yaml` through four checks
**before** you launch, so those failures surface in seconds:

1. **REGISTRY** — the name is in `denario.llm.max_output_tokens_dict`. If not,
   every stage that uses it `KeyError`s at parse time.
2. **TEMP** — the role has a `temperature:` key. `llm_parser` reads
   `llm['temperature']` with **no default**, so a role omitting it dies with
   `KeyError: 'temperature'` at stage setup (the reference example sets it on
   *every* role for this reason — copy that, don't drop it).
3. **KEY** — the provider inferred from the name (same rule as cmbagent_lg:
   `gemini-*`→`GOOGLE_API_KEY`, `gpt-*`/`o[1-4]*`→`OPENAI_API_KEY`,
   `claude-*`→`ANTHROPIC_API_KEY`) has its key in the environment.
4. **LIVE** — builds the chat model via `cmbagent_lg.llms.chat_model` and sends a
   one-token ping, confirming the key/model pair is actually accepted (catches
   revoked keys, no-access models, billing/credit problems). Skip with `--offline`.

The test **reuses Denario's own registry and provider logic** (imports
`denario.llm` + `cmbagent_lg.llms`), so a PASS means what the pipeline will see.

## How to run

The bundled `firetest.py` lives next to this file. Run it on the **same
interpreter the Denario MCP servers are registered with** (the cmbagent_lg venv)
so the registry and the API keys it sees match the real run:

```bash
LGPY=/Users/boris/pyvenvs/py312-cmbagent-lg/bin/python
FT="${CLAUDE_PLUGIN_ROOT}/skills/firetest/firetest.py"   # or this file's dir + /firetest.py

# Point it at the project's params.yaml (or just the project dir — it'll find params.yaml):
$LGPY "$FT" <project_dir>/params.yaml

# Fast offline pass (registry + keys only, no API calls):
$LGPY "$FT" <project_dir>/params.yaml --offline

# Per-model live-ping timeout (seconds), default 30:
$LGPY "$FT" <project_dir>/params.yaml --timeout 45
```

If `$ARGUMENTS` is a directory, use `<dir>/params.yaml`. Confirm the keys are
present in the **MCP server's** environment, not just your shell — that's the env
the pipeline actually uses (see the `conventions` / `explain` skills).

## Reading the result

A table, one row per unique model (with a `USES` count of how many roles share
it), then `PASS`/`FAIL` and exit code `0`/`1`:

- `REG MISSING` → the name isn't registered. Add it to `denario/llm.py`
  `max_output_tokens_dict`, or switch to a registered, **non-preview** name
  (`gemini-3.5-flash`, `gemini-3.1-flash-lite`, `gpt-5.4`, `claude-sonnet-4-6`).
- `TEMP MISS xN` → N role(s) sharing that model omit `temperature:` (the detail
  line names them). Add `temperature: <float>` to each — without it `llm_parser`
  raises `KeyError: 'temperature'` the moment that stage starts.
- `NO <KEY>` → export that API key in the MCP server's environment.
- `LIVE FAIL` → the key/model pair was rejected; the detail line shows the error
  (auth, no model access, rate/credit limit).
- `local` provider (e.g. `Qwen/...`, `nvidia/...`) → an OpenAI-compatible local
  endpoint. Registered and counted, but the live ping is skipped — its
  `*_BASE_URL` server must be up to truly test it.

**On FAIL, fix the flagged rows before running any `denario_*` stage** — don't
launch a run you know will break. On PASS, proceed with the pipeline.
