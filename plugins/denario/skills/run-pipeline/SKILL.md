---
description: Run the Denario research pipeline end-to-end over MCP — lay out a project from a data description, then idea → (literature) → methods → results → evaluate/iterate → paper → (classify/publish), configured via params.yaml. Use when the user wants a full research run (not just one stage).
disable-model-invocation: true
argument-hint: "<project_dir> [data description or path] [hints: --steps=4 --vlm --literature --iterate=2 --no-citations --publish]"
allowed-tools: Read Write Edit Glob Grep Bash mcp__denario__denario_idea mcp__denario__denario_literature mcp__denario__denario_methods mcp__denario__denario_results mcp__denario__denario_evaluate mcp__denario__denario_paper mcp__denario__denario_classify mcp__denario__denario_publish mcp__denario__denario_audio_summary mcp__denario__denario_status mcp__denario__denario_read_file mcp__denario__denario_list_files
---

# Run the Denario pipeline

Drive the full Denario pipeline for the project at `$0` through the **denario MCP tools**.
Read the [`explain`](../explain/SKILL.md) skill for tool details and the
[`conventions`](../conventions/SKILL.md) skill for operating rules (privacy, git, paths,
iteration) — both apply here. **Confirm any underspecified choice with the user before
launching a long run — don't guess the science**, and ask before anything outward-facing
(public repo, publish).

Drive **each stage as a separate tool call** so a failure is localized; don't bundle. Watch
`/tmp/denario-mcp.log` during the long stages.

## Steps

1. **Prepare the project** (avoid `denario_setup` unless the user wants a GitHub repo):
   - `mkdir -p $0/Iteration0/input_files`
   - Write the **data description** to `$0/Iteration0/input_files/data_description.md` (from
     `$ARGUMENTS`, a referenced file, or by asking). **Reference the data file by its full
     absolute path, wherever it actually lives** — the data folder is the user's, untouched
     by Denario, and need not be inside the project tree. Never use a relative path: generated
     code executes with `cwd = $0/Iteration<N>/experiment_output/`, so a path relative to the
     project root resolves against the wrong directory and the load fails.
   - Put a **`params.yaml`** at `$0/params.yaml`. Start from
     `Denario/tests/params_multiprovider.yaml` (or `denario-scientists/data/params.yaml`)
     and set, in the `Analysis module`: `max_n_steps: 3`–`4` (small unless asked), current
     **non-preview** models (e.g. `gemini-3.5-flash`, `gpt-5.4`, `claude-sonnet-4-6`; each
     must be in `denario/llm.py`), and `enable_vlm_review: true` (+ `vlm_model:
     gemini-3.1-flash-lite`) if `--vlm`.
   - Ensure the matching API keys are in the server env (`GOOGLE_API_KEY`, plus
     `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` for those providers).

2. **Idea** → `denario_idea(project_dir=$0)`. Read `input_files/idea.md`; show a 1-line summary.

3. **Literature** *(only if `--literature`)* → `denario_literature(project_dir=$0)`. Reports
   novelty vs. existing work (Semantic Scholar / FutureHouse) into `literature.md`. Summarize.

4. **Methods** → `denario_methods(project_dir=$0)`. Summarize `methods.md`.

5. **Results** → `denario_results(project_dir=$0)`. **Long** (minutes); runs cmbagent_lg.
   - Set a generous MCP read timeout if your client supports it.
   - Watch `/tmp/denario-mcp.log` for `[cmbagent_lg]` banners and `deep_research COMPLETE (n/n steps)`.
   - On a transient failure, `denario_results(project_dir=$0, restart_at_step=N)` resumes from
     the checkpoint (`N = last fulfilled step + 1`, from
     `experiment_output/logs/deep_research_run.json`) — don't re-plan from scratch.

6. **Evaluate / iterate** *(only if `--iterate=K`, default: skip)* — repeat up to **K** times,
   or until the evaluator is satisfied / `max_iterations` is hit:
   - `denario_evaluate(project_dir=$0)` → writes `hypothesis.md` (what to change).
   - If it asks for another iteration: re-run **methods** then **results** for the next
     iteration (results reuse unchanged steps via the checkpoint). Report the delta each round.
   - Use `denario_status(project_dir=$0)` to track the **best** iteration; write the paper from it.

7. **Paper** → `denario_paper(project_dir=$0, add_citations=True)`. **Citations are on by
   default** (standard output: `paper_v3_citations` → `paper_v4_final`); pass
   `add_citations=False` only if `--no-citations`. `cmbagent_keywords` stays `False` (legacy
   cmbagent). Confirm `paper.pdf` exists.

8. **Classify** *(optional)* → `denario_classify(project_dir=$0)` — arXiv category/subcategory.

9. **Publish** *(only if `--publish`, and only after confirming with the user)* →
   `denario_publish(project_dir=$0)` builds GitHub Pages + updates the README. For a private
   project, get explicit confirmation to make it public first (see `conventions`).

10. **Audio** *(optional, `--audio`)* → `denario_audio_summary(project_dir=$0, stage=…)`.

11. **Report back**: the idea (1 line); literature verdict if run; n results steps + whether
    all fulfilled; number of plots propagated; iterations run + best one; the `paper.pdf` path
    + size; and the published URL if any. Flag any stage that halted and why (from the log /
    `denario_status`).

## Notes
- **Default run** (no flags) = idea → methods → results → paper. Literature, iteration,
  classify, publish, and audio are opt-in via the flags above.
- `denario_eda` and the cmbagent-keyword paper path need the **legacy cmbagent** package (not
  in the cmbagent-lg venv) — skip them.
- Keep `max_n_steps` small for iteration; raise it once the science is dialed in.
