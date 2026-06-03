---
description: Operating conventions for running Denario research over MCP — how to report stage output, where logs/outputs live, the privacy + git/publish rules, and the evaluate→iterate loop. Use alongside the pipeline tools so a Denario run behaves predictably and safely.
when_to_use: User is running any denario_* / cmbagent_lg_* MCP tool, driving the Denario pipeline, asking where a stage's output or log is, about project privacy/visibility, publishing (GitHub Pages), committing results, or iterating (evaluate → new iteration). Pairs with the `explain` skill (tool/params knowledge) and `run-pipeline` (end-to-end execution).
allowed-tools: Read Grep Glob
---

# Denario operating conventions

These are the behavioral rules for driving Denario well in an interactive Claude Code
session. The [`explain`](../explain/SKILL.md) skill covers *what* the tools do and the
`params.yaml` surface; this skill covers *how to operate* — reporting, paths, privacy,
git, and iteration. (Ported from the autonomous-scientist `SOUL.md`/`AGENTS.md`, minus
the OpenClaw/Slack/container specifics that don't apply to a local Claude Code run.)

## Stage discipline

- **One stage per turn.** Drive each `denario_*` stage as its own tool call so a failure
  is localized. Don't chain idea→methods→results in a single step.
- **Long & synchronous.** Most pipeline tools run for minutes (`denario_results` longest).
  After each call, **report the actual outcome** — don't claim success without checking.
- **Read, don't assume.** Inspect what a stage produced with `denario_read_file` /
  `denario_list_files` (or plain `Read`/`Glob`) before moving on. Never describe a result
  you haven't read.
- **Where things land** (per project, per iteration):
  - Console logs: `<project_dir>/logs/<step>.log` — tail `/tmp/denario-mcp.log` for the
    live `[cmbagent_lg]` banners during `denario_results`.
  - Structured output: `<project_dir>/Iteration<N>/<step>_output/`.
  - Stage docs: `<project_dir>/Iteration<N>/input_files/{data_description,idea,methods,results}.md`.
  - Figures: `<project_dir>/Iteration<N>/.../plots/` — only plots from **successful** steps
    propagate to the paper.
  - Use `denario_status(project_dir)` to see completeness + the best iteration.

## Privacy & publishing (ask before anything outward-facing)

- **Default to private.** New projects via `denario_setup` should be `private=True`. Only
  pass `private=False` when the user explicitly asks for a public repo.
- **`denario_setup` creates a real GitHub repo** (and `git init`s). If the user doesn't
  want that side effect, lay the project out by hand instead — `mkdir -p
  Iteration0/input_files`, write `data_description.md`, drop a `params.yaml` — and skip
  `denario_setup` entirely.
- **Confirm before publishing.** `denario_publish` builds GitHub Pages and flips repo
  visibility/README. For a private project, **ask the user to confirm** making it public
  before you publish. Publishing is hard to walk back (caching/indexing).

## Git behavior

- The pipeline tools **auto-commit and push** after each step. Surface the marker the tool
  returns rather than re-interpreting it:
  - `GIT_OK:` committed + pushed.
  - `GIT_SKIP:` nothing to commit / not a git repo.
  - `GIT_PUSH_FAILED:` committed locally, push failed (auth/network).
- **Never halt the research pipeline for a git push failure.** Note it, keep going, and
  let the user resolve the remote later.

## The evaluate → iterate loop

Denario improves a result over iterations, not in one shot:

1. `denario_evaluate(project_dir)` judges the current iteration and writes a `hypothesis.md`
   (what to change next).
2. The next iteration regenerates **methods** from that feedback, then re-runs **results** —
   reusing unchanged steps automatically (the cmbagent_lg checkpoint), not from scratch.
3. Repeat until the evaluator is satisfied or you hit `max_iterations` (top-level in
   `params.yaml`). Then write the paper from the **best** iteration (`denario_status` reports it).

Keep `Analysis module: max_n_steps` small (3–4) while iterating; raise it once the science
is dialed in.

## Never fabricate

Do **not** invent data, manufacture results to replace a failed analysis, hardcode expected
outputs, or write code that produces fake "results" to make a step look successful. This
applies to plots, statistics, tables, and every quantitative claim in the paper. **A failed
experiment honestly reported is more valuable than a fabricated success.** If an analysis
fails, report the failure — don't work around it by producing output.

## When a stage fails — read, stop, don't paper over it

After `denario_results`, **inspect `results.md`** before going further. The analysis did
**not** succeed (do not proceed to evaluate/paper/publish) if:
- `results.md` contains raw code instead of a researcher-written Results section, or
- it shows steps failed (e.g. "Max number of code execution attempts reached").

In that case: read the console log (`<project_dir>/logs/<step>.log`), tell the user which
step failed and why, propose a fix (different approach, relaxed constraints, more attempts),
and **wait** — don't auto-retry the same thing.

More stop conditions:
- **Rate-limit / credit errors** (`429 Too Many Requests`, `RateLimitError`,
  `insufficient_quota`, "billing hard limit reached"): **stop immediately**, don't retry in a
  loop (it wastes time and may incur charges). Report the exact error and what remains.
- **Repeated identical failures**: if the engineer keeps hitting the same traceback,
  incremental fixes aren't working — **change strategy**, don't restart the same step. "Fails
  twice the same way ⇒ change approach."

### Classification must not fall back to a default

If `denario_classify` errors, **never** accept or write a default arXiv category. It's
idempotent (Title/Abstract/Methods are already on disk) — read its log, retry, and if it
still fails, report and **wait**. Do not hand-write `classification.json`, and do not
`denario_publish` without a valid classification.

## New idea = new project

When the user wants to "try something else" / "start over" / a different research direction
on the same data, create a **new** `project_dir` (e.g. `…_v2`) starting fresh from setup —
don't reuse the existing project. (This is distinct from the iterate loop above, where the
hypothesis evolves *within* one project from evaluator feedback.)

## Recovery

`denario_results` checkpoints after every step to
`…/experiment_output/logs/deep_research_run.json`. After a crash, resume with
`denario_results(restart_at_step=N)` where **N = max(fulfilled step_number) + 1** (read it
from that JSON). Don't re-plan from scratch — that throws away completed steps.

## Model / params sanity

- Use **current, non-preview** model names (`gemini-3.5-flash`, `gemini-3.1-flash-lite`,
  `gpt-5.4`, `claude-sonnet-4-6`). A model must also be in Denario's `denario/llm.py`
  registry or `llm_parser` raises `KeyError`.
- Each role's provider is inferred from the model name; the matching API key
  (`GOOGLE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) must be in the MCP server's
  environment. See [`explain`](../explain/SKILL.md) → `reference.md`.

## Out of scope (needs the legacy `cmbagent` package)

`denario_eda` and the `cmbagent_keywords` paper path are **not** in the cmbagent-lg venv and
will error. Skip them in a cmbagent-lg setup.
