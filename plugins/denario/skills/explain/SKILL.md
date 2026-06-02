---
description: How to drive the Denario research assistant over MCP — the end-to-end pipeline (setup → idea → methods → results → paper), configuring models/steps/VLM via params.yaml, and the cmbagent_lg analysis engine (plan/execute/restart, crash-recoverable). Use when the user wants to run Denario, call a denario_* or cmbagent_lg_* MCP tool, generate a research idea/methods/results/paper, or configure params.yaml.
when_to_use: User mentions Denario, the denario MCP, denario_results / denario_idea / denario_methods / denario_paper / denario_setup, cmbagent_lg (plan/execute/restart), running the research pipeline, generating a scientific idea/method/result/paper from a data description, params.yaml for analysis models, enable_vlm_review, or restart_at_step.
allowed-tools: Read Grep Glob
---

# Using the Denario MCP

Denario is a multi-agent research assistant (docs: https://denario.readthedocs.io · source: https://github.com/AstroPilot-AI/Denario). It turns a **data description** into a full research output — idea → methodology → results (analysis + plots) → a written paper — and exposes every stage as an **MCP tool**. The analysis/results stage runs on the **cmbagent_lg** LangGraph engine.

There are **two MCP servers**:

| Server | Tools | Use for |
|---|---|---|
| **`denario`** | `denario_setup`, `denario_idea`, `denario_methods`, `denario_results`, `denario_paper`, `denario_evaluate`, `denario_classify`, `denario_status`, `denario_read_file`, `denario_list_files`, … | the **full pipeline** on a project directory |
| **`cmbagent_lg`** | `cmbagent_lg_plan`, `cmbagent_lg_execute`, `cmbagent_lg_restart`, `cmbagent_lg_status`, `cmbagent_lg_get_plan` | the **analysis engine** directly (plan/execute/restart a single task), background + status-poll |

(In a Claude Code session the tools appear namespaced, e.g. `mcp__denario__denario_results`.)

## The pipeline (denario server)

Each stage reads/writes a **project directory** laid out as `Iteration{N}/input_files/{data_description,idea,methods,results}.md`, plus `plots/` and `experiment_output/`. Drive the stages in order:

1. **`denario_setup(data_description, project_dir, repo_slug="…")`** — create the project + write `data_description.md`. ⚠️ it also `git init`s and **creates a GitHub repo**; if you don't want that, lay the files out by hand instead (`mkdir -p Iteration0/input_files`, write `data_description.md`, drop a `params.yaml`).
2. **`denario_idea(project_dir)`** → `idea.md` (LangGraph).
3. **`denario_methods(project_dir)`** → `methods.md` (LangGraph).
4. **`denario_results(project_dir)`** — **the heart**: runs cmbagent_lg (planning + step-by-step execution) on the idea+methods+data, writes `results.md` (a researcher-authored Results section) and moves the generated figures into `plots/`. Synchronous and long (minutes); watch `/tmp/denario-mcp.log`.
5. **`denario_paper(project_dir, add_citations=False)`** → builds `paper.tex` + `paper.pdf` (LangGraph + latexmk). Set `add_citations=True` for the citation passes; `cmbagent_keywords=False` is the default (the keyword path needs the legacy cmbagent).

`denario_status(project_dir)` reports progress; `denario_read_file` / `denario_list_files` inspect outputs.

> Stages **idea / methods / paper** run on LangGraph; **results** runs on cmbagent_lg; **EDA and the cmbagent keyword path** still depend on the legacy `cmbagent` package and will error if it isn't installed in the server's venv.

## params.yaml is the control surface

Everything about *how* a stage runs is set per-module in `params.yaml` (passed via `params_file=` or found at `{project_dir}/params.yaml`). The **`Analysis module`** controls the results stage:

```yaml
Analysis module:
   max_n_steps: 4            # keep small for tests (3–4), not 8–10
   max_n_attempts: 10
   code_execution_timeout: 300
   # Per-role models — provider inferred from the NAME
   # (gemini-* → Google, gpt-*/o[1-4]* → OpenAI, claude-* → Anthropic).
   engineer:      { model: gemini-3.5-flash, temperature: 0.1 }   # writes+runs code
   researcher:    { model: gpt-5.4,          temperature: 0.1 }   # writes Results section
   planner:       { model: gemini-3.5-flash, temperature: 0.1 }
   plan_reviewer: { model: claude-sonnet-4-6 }
   evaluator:     { model: claude-sonnet-4-6 }                    # judges each step
   # Multimodal grounding (cmbagent_lg image-reviewer + researcher sees plots)
   enable_vlm_review: true
   vlm_model:     { model: gemini-3.1-flash-lite }                # vision-capable
   max_vlm_review_attempts: 2
```

Key points:
- **Multi-provider in one run** is fine — each role's provider is inferred from the model name. The matching API key must be in the server's env: `GOOGLE_API_KEY` (Gemini), `OPENAI_API_KEY` (gpt/o-series), `ANTHROPIC_API_KEY` (claude).
- Use **current, non-preview** model names. `gemini-3.5-flash` is the newest non-preview Gemini; `gemini-3.1-flash-lite` for cheap/vision; `gpt-5.4`; `claude-sonnet-4-6` (there is no Claude *Sonnet* 4.7 — only Opus goes to 4.7/4.8). A model must also be in Denario's `denario/llm.py` registry or `llm_parser` raises `KeyError`.
- For **quick tests, set `max_n_steps: 3–4`.**

## The cmbagent_lg engine (direct, low-level)

`denario_results` wraps cmbagent_lg, but you can drive the engine directly for a single task — useful for iterating on a plan or resuming a crashed run:

- **`cmbagent_lg_plan(task, work_dir, …)`** — generate + save a plan (`planning/final_plan.json`). Accepts the same per-role model and VLM overrides; persists them so execute/restart reuse them.
- **`cmbagent_lg_execute(work_dir)`** — run the plan in the **background**, returns a `run_id`.
- **`cmbagent_lg_status(run_id)`** — poll progress (current step, outcomes).
- **`cmbagent_lg_restart(work_dir, restart_at_step=N)`** — resume from step N, reusing earlier steps' artifacts.
- **`cmbagent_lg_get_plan(work_dir)`** — read the saved plan.

## Restart / crash recovery (important)

The engine **checkpoints after every step** to `…/experiment_output/logs/deep_research_run.json`. So a run is resumable:
- `denario_results(restart_at_step=N)` (or `cmbagent_lg_restart`) resumes from step N with full prior context — earlier steps are **not** re-run.
- To find N after a crash, read `deep_research_run.json` and take **`max(fulfilled step_number) + 1`**.
- `denario_results`' own retry loop already auto-resumes from the checkpoint on transient errors (timeouts/connection drops); it only re-plans from scratch when there's no checkpoint.

## Gotchas

- **Venv:** the MCP servers run on the `py312-cmbagent-lg` interpreter (has cmbagent_lg + Denario + modern langchain). They self-load `GOOGLE_API_KEY` from `~/GitHub/cmbagent_lg/.env`; add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` there (or to the MCP registration `env`) to use those providers.
- **`denario_results` is synchronous and long.** When driving it over an MCP client, allow a long read timeout. For non-blocking runs use the `cmbagent_lg_execute` + `cmbagent_lg_status` pattern instead.
- **Output convention:** the engineer writes all artifacts (plots, tables, data) flat under `data/`; only those are tracked. Plots from *successful* steps are what propagate to the paper.
- **Don't launch the servers from `~/GitHub`** — a `cmbagent_lg/` or `Denario/` checkout there shadows the installed package. The servers guard against this, but if you run anything by hand, `cd` elsewhere first.

## Going deeper

For the full MCP tool reference (every tool + signature), the complete `params.yaml` schema (all modules), the output directory layout, and registering the servers with Claude Code, see [reference.md](reference.md).

To run the whole pipeline end-to-end with one command, use **`/denario:run-pipeline`**.
