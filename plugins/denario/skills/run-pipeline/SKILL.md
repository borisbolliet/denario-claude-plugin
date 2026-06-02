---
description: Run the Denario research pipeline end-to-end over MCP — lay out a project from a data description, then idea → methods → results → paper, configured via params.yaml. Use when the user wants a full research run (not just one stage).
disable-model-invocation: true
argument-hint: "<project_dir> [data description or path] [hints: --steps=4 --vlm --no-citations …]"
allowed-tools: Read Write Edit Glob Grep Bash mcp__denario__denario_idea mcp__denario__denario_methods mcp__denario__denario_results mcp__denario__denario_paper mcp__denario__denario_status mcp__denario__denario_read_file
---

# Run the Denario pipeline

Drive the full Denario pipeline for the project at `$0` through the **denario MCP
tools**. Read [the explain skill](../explain/SKILL.md) first if you need the tool
details. Confirm any underspecified choice with the user before launching a long
run — don't guess the science.

## Steps

1. **Prepare the project** (avoid `denario_setup` unless the user wants a GitHub repo):
   - `mkdir -p $0/Iteration0/input_files`
   - Write the **data description** to `$0/Iteration0/input_files/data_description.md` (from `$ARGUMENTS`, a referenced file, or by asking).
   - Put a **`params.yaml`** at `$0/params.yaml`. Start from `Denario/tests/params_multiprovider.yaml` (or `denario-scientists/data/params.yaml`) and set, in the `Analysis module`:
     - `max_n_steps: 3` or `4` (small unless the user wants more),
     - current **non-preview** models (e.g. `gemini-3.5-flash`, `gpt-5.4`, `claude-sonnet-4-6`) — and ensure each is in `denario/llm.py`'s registry,
     - `enable_vlm_review: true` (+ `vlm_model: gemini-3.1-flash-lite`) if `--vlm`.
   - Make sure the matching API keys are available to the server (`GOOGLE_API_KEY`, and `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` for those providers).

2. **Idea** → `denario_idea(project_dir=$0)`. Then read `input_files/idea.md` and show a 1-line summary.

3. **Methods** → `denario_methods(project_dir=$0)`. Summarize `methods.md`.

4. **Results** → `denario_results(project_dir=$0)`. This is **long** (minutes) and runs cmbagent_lg.
   - If your MCP client supports it, set a generous read timeout.
   - Watch `/tmp/denario-mcp.log` for the `[cmbagent_lg]` banners and `deep_research COMPLETE (n/n steps)`.
   - On a transient failure, `denario_results(restart_at_step=N)` resumes from the checkpoint (`N = last fulfilled step + 1`, read from `experiment_output/logs/deep_research_run.json`).

5. **Paper** → `denario_paper(project_dir=$0, add_citations=False)` (pass `add_citations=True` only if `--citations`). Confirm `paper.pdf` exists.

6. **Report back**: the idea (1 line), n results steps + whether all fulfilled, number of plots propagated, and the `paper.pdf` path + size. Note any stage that halted and why (from the log / `denario_status`).

## Notes
- `denario_eda` and the cmbagent-keyword paper path need the **legacy cmbagent** package (not in the cmbagent-lg venv) — skip them.
- Drive each stage as a separate tool call so a failure is localized; don't bundle.
- Keep `max_n_steps` small for iteration; raise it once the science is dialed in.
