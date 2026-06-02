# Denario MCP — reference

Deep reference for the two MCP servers, the `params.yaml` schema, the on-disk
layout, and server registration. The [SKILL.md](SKILL.md) has the workflow; this
is the lookup table.

## `denario` server — tool signatures

All operate on a `project_dir` and a project iteration (`Iteration{N}/`).

| Tool | Signature | Notes |
|---|---|---|
| `denario_setup` | `(data_description, project_dir, repo_slug="", params_file=None, project_iteration=0)` | writes `data_description.md`; **also git-inits + creates a GitHub repo** |
| `denario_eda` | `(project_dir, params_file=None, project_iteration=0)` | exploratory analysis — **legacy cmbagent** (needs it installed) |
| `denario_idea` | `(project_dir, params_file=None, project_iteration=0, EDA_report=False, human_feedback=None)` | LangGraph → `idea.md` |
| `denario_literature` | `(project_dir, …, mode='semantic_scholar')` | novelty check (FutureHouse path removed; use semantic_scholar) |
| `denario_methods` | `(project_dir, params_file=None, project_iteration=0)` | LangGraph → `methods.md` |
| `denario_results` | `(project_dir, params_file=None, project_iteration=0, hardware_constraints=None, restart_at_step=-1)` | **cmbagent_lg** → `results.md` + plots. Synchronous/long |
| `denario_evaluate` | `(project_dir, params_file=None, project_iteration=0)` | grade results, decide whether to iterate |
| `denario_paper` | `(project_dir, params_file=None, project_iteration=-1, just_abstract=False, add_citations=False)` | LangGraph + latexmk → `paper.tex`/`paper.pdf` |
| `denario_classify` | `(project_dir, params_file=None, project_iteration=-1)` | arXiv-category classification |
| `denario_status` | `(project_dir)` | progress/completeness |
| `denario_publish` | `(project_dir, project_iteration=-1)` | build GitHub Pages site + push |
| `denario_audio_summary` | `(project_dir, stage, params_file=None, project_iteration=0, text="")` | ElevenLabs TTS summary of a stage |
| `denario_read_file` | `(path)` | read a project file |
| `denario_list_files` | `(path, pattern="*.md")` | list project files |

Server log: `/tmp/denario-mcp.log` (override `DENARIO_MCP_LOG`).

## `cmbagent_lg` server — tool signatures

| Tool | Signature | Notes |
|---|---|---|
| `cmbagent_lg_plan` | `(task, work_dir, max_plan_steps=5, num_rounds=1, hardware_constraints=…, code_execution_timeout=120, max_n_attempts=3, engineer_only=True, enable_escalation=False, escalation_model=None, planner_model=None, plan_reviewer_model=None, engineer_model=None, researcher_model=None, evaluator_model=None, enable_vlm_review=False, vlm_model=None, max_vlm_review_attempts=2)` | sync; saves `planning/final_plan.json` + `planning/run_context.json` |
| `cmbagent_lg_execute` | `(work_dir)` | **background** → `{run_id, status:"running"}` |
| `cmbagent_lg_restart` | `(work_dir, restart_at_step)` | background; resume at step N |
| `cmbagent_lg_status` | `(run_id)` | poll in-memory run state |
| `cmbagent_lg_get_plan` | `(work_dir)` | read back the saved plan |

`run_context.json` persists the full `PlanContext` (models, VLM, timeouts), so
`execute`/`restart` reuse whatever `plan` set. Server log: `/tmp/cmbagent-lg-mcp.log`
(override `CMBAGENT_LG_MCP_LOG`).

## `params.yaml` — full structure

Denario reads `params.yaml` as a dict of **modules**, one per pipeline stage.
Inside a module, each **named agent** is an entry `{ model: <name>, temperature:
<float> }` — the **provider is inferred from the model name**. Stage-level scalar
hyperparameters (`max_n_steps`, `max_n_attempts`, `code_execution_timeout`,
`enable_vlm_review`, …) sit at the top of the module. A few top-level keys live
outside any module.

Reference files: `Denario/tests/params_multiprovider.yaml` (compact, multi-provider)
and `denario-scientists/data/params.yaml` (full production set).

### Every module — which tool/backend uses it, and its agents

| Module / key | Stage (tool) | Backend | Agents / keys |
|---|---|---|---|
| `max_iterations` (top level) | the iterate loop | — | int — max idea→…→evaluate cycles |
| `hardware_constraints` (top level) | results/EDA planners | — | free-text machine description |
| **`EDA module`** | `denario_eda` | **legacy cmbagent** | `engineer`, `researcher`, `planner`, `plan_reviewer`, `orchestration`, `evaluator` + `max_n_steps`, `max_n_attempts`, `code_execution_timeout`, `enable_vlm_review` |
| **`Idea module`** | `denario_idea` | LangGraph | `idea_sampler`, `idea_selector1/2/3`, `idea_chooser`, `idea_maker`, `idea_hater` |
| **`Literature module`** | `denario_literature` | LangGraph | `literature`, `summarizer` |
| **`Methods module`** | `denario_methods` | LangGraph | `methods`, `reviewer1/2/3`, `improver` |
| **`Analysis module`** | `denario_results` | **cmbagent_lg** | `engineer`, `researcher`, `planner`, `plan_reviewer`, `evaluator`, `orchestration` (unused) + `max_n_steps`, `max_n_attempts`, `code_execution_timeout`, `enable_vlm_review`, `vlm_model`, `max_vlm_review_attempts` |
| **`Evaluator module`** | `denario_evaluate` | LangGraph | `reporter`, `idea_reviewer`, `methods_reviewer`, `input_reviewer`, `new_iteration_reviewer`, `results_reviewer` |
| **`Paper module`** | `denario_paper` | LangGraph | `keywords_writer`, `section_writer`, `refiner`, `audio_summarizer` |
| **`Citations`** | `denario_paper(add_citations=True)` | LangGraph | `backend` (`valency`/`perplexity`), `citation_inserter` |
| **`Classifier module`** | `denario_classify` | LangGraph | `archive_classifier`, `subcategory_classifier` |
| **`Reviewer module`** | paper review | LangGraph | `reviewer1/2/3`, `meta_reviewer` |

Notes:
- **Only `Analysis module` drives cmbagent_lg** (the results engine); its roles map to the cmbagent_lg agents in the table further down. `vlm_model` + `max_vlm_review_attempts` are cmbagent_lg-specific.
- **`EDA module`** runs on the legacy cmbagent package (not in the cmbagent-lg venv) — it errors there.
- A model named in any module you actually run must be in `denario/llm.py`'s registry, else `llm_parser` raises `KeyError`.

### Annotated example (the stages you typically run)

```yaml
max_iterations: 12
hardware_constraints: "Standard laptop. Single CPU. No GPU."

Idea module:                 # denario_idea (LangGraph fast mode)
   idea_sampler:    { model: gemini-3.1-flash-lite, temperature: 0.7 }
   idea_selector1:  { model: gemini-3.1-flash-lite, temperature: 0.1 }
   idea_selector2:  { model: gemini-3.1-flash-lite, temperature: 0.1 }
   idea_selector3:  { model: gemini-3.1-flash-lite, temperature: 0.1 }
   idea_chooser:    { model: gemini-3.1-flash-lite, temperature: 0.1 }
   idea_maker:      { model: gemini-3.1-flash-lite, temperature: 0.7 }
   idea_hater:      { model: gemini-3.1-flash-lite, temperature: 0.1 }

Methods module:              # denario_methods (LangGraph)
   methods:    { model: gemini-3.1-flash-lite, temperature: 0.1 }
   reviewer1:  { model: gemini-3.1-flash-lite, temperature: 0.1 }
   reviewer2:  { model: gemini-3.1-flash-lite, temperature: 0.2 }
   reviewer3:  { model: gemini-3.1-flash-lite, temperature: 0.2 }
   improver:   { model: gemini-3.1-flash-lite, temperature: 0.2 }

Analysis module:             # denario_results (cmbagent_lg)
   max_n_steps: 4            # small for tests (3–4), not 8–10
   max_n_attempts: 10
   code_execution_timeout: 300
   engineer:      { model: gemini-3.5-flash, temperature: 0.1 }
   researcher:    { model: gpt-5.4,          temperature: 0.1 }
   planner:       { model: gemini-3.5-flash, temperature: 0.1 }
   plan_reviewer: { model: claude-sonnet-4-6 }
   orchestration: { model: gemini-3.1-flash-lite }   # read but unused
   evaluator:     { model: claude-sonnet-4-6 }
   enable_vlm_review: true
   vlm_model:     { model: gemini-3.1-flash-lite }   # vision-capable
   max_vlm_review_attempts: 2

Paper module:                # denario_paper (LangGraph + latexmk)
   keywords_writer:  { model: gemini-3.1-flash-lite, temperature: 0.1 }
   section_writer:   { model: gemini-2.5-pro,        temperature: 0.1 }
   refiner:          { model: gemini-2.5-pro,        temperature: 0.1 }
   audio_summarizer: { model: gemini-3.1-flash-lite, temperature: 0.3 }

Citations:                   # only when denario_paper(add_citations=True)
   backend: valency           # or 'perplexity'
   citation_inserter: { model: gemini-3.1-flash-lite, temperature: 0.1 }

Evaluator module:            # denario_evaluate
   reporter:               { model: gemini-3.1-flash-lite, temperature: 0.1 }
   idea_reviewer:          { model: gemini-3.1-flash-lite, temperature: 0.2 }
   methods_reviewer:       { model: gemini-3.1-flash-lite, temperature: 0.2 }
   input_reviewer:         { model: gemini-3.1-flash-lite, temperature: 0.2 }
   new_iteration_reviewer: { model: gemini-3.1-flash-lite, temperature: 0.1 }
   results_reviewer:       { model: gemini-3.1-flash-lite, temperature: 0.2 }

Classifier module:          # denario_classify
   archive_classifier:     { model: gemini-3.1-flash-lite, temperature: 0.1 }
   subcategory_classifier: { model: gemini-3.1-flash-lite, temperature: 0.1 }

Reviewer module:            # paper review
   reviewer1:     { model: gemini-3.1-flash-lite, temperature: 0.2 }
   reviewer2:     { model: gemini-3.1-flash-lite, temperature: 0.2 }
   reviewer3:     { model: gemini-3.1-flash-lite, temperature: 0.2 }
   meta_reviewer: { model: gemini-3.1-flash-lite, temperature: 0.2 }

# EDA module: …            # denario_eda — legacy cmbagent (not in the lg venv)
# Literature module: …     # denario_literature (literature, summarizer)
```

### Model-name rules
- Provider by prefix: `gemini-*` → Google (`GOOGLE_API_KEY`), `gpt-*`/`o1`/`o3`/`o4` → OpenAI (`OPENAI_API_KEY`), `claude-*` → Anthropic (`ANTHROPIC_API_KEY`).
- OpenAI o-series reasoning models reject `temperature`; cmbagent_lg omits it automatically.
- Gemini `thinking_level` is passed only for `gemini-3*` (2.x rejects it).
- Every model used by a stage must be in **`denario/llm.py:max_output_tokens_dict`**, else `llm_parser` raises `KeyError: 'model …'`. Add new model names there.
- Known-good non-preview names: `gemini-3.5-flash`, `gemini-3.1-flash-lite`, `gpt-5.4`, `claude-sonnet-4-6`, `claude-opus-4-7/4-8`.

## cmbagent_lg roles (what each model does in the results stage)

| params.yaml role | cmbagent_lg role | job |
|---|---|---|
| `planner` | planner (generator) | designs the multi-step plan |
| `plan_reviewer` | critic | critiques the plan |
| `engineer` | engineer (generator) | writes + runs the analysis code |
| `researcher` | researcher (generator) | writes the Results-section report |
| `evaluator` | execution + step evaluators (critic) | did the code run / meet the goal |
| `vlm_model` | image_reviewer | visually reviews the figures (bounded revise-the-plot loop) |

## Output layout (per iteration)

```
{project_dir}/Iteration{N}/
├── input_files/
│   ├── data_description.md   idea.md   methods.md   results.md
│   └── plots/                 # figures propagated from successful steps
└── experiment_output/         # cmbagent_lg work dir
    ├── planning/final_plan.json   run_context.json
    ├── codebase/step_*.py / .log
    ├── data/                  # engineer outputs (flat; only these are tracked)
    ├── reports/step_*.md      # researcher reports (results.md = last one)
    └── logs/deep_research_run.json   # the per-step CHECKPOINT (restart reads this)
{project_dir}/paper.tex   paper.pdf      # after denario_paper
```

## Registering the servers with Claude Code

Run both on the cmbagent_lg venv, by **absolute script path** (not `-m`), so the
in-module shadow guard runs before the package import:

```bash
LGPY=/Users/boris/pyvenvs/py312-cmbagent-lg/bin/python
DEN=/Users/boris/GitHub/Denario/denario/mcp_servers

claude mcp add denario     -s user -- $LGPY $DEN/denario_server.py
claude mcp add cmbagent_lg -s user -- $LGPY $DEN/cmbagent_lg_server.py
# add -e OPENAI_API_KEY=… -e ANTHROPIC_API_KEY=… if using those providers
```

Then `/mcp` to confirm both show **✓ Connected**, and restart the session so the
tools load. The servers self-load `GOOGLE_API_KEY` (+ `LANGFUSE_*`) from
`~/GitHub/cmbagent_lg/.env` (override path with `CMBAGENT_LG_ENV`).

## Stages still on legacy cmbagent

`denario_eda` and the paper "cmbagent keywords" path import the legacy `cmbagent`
package. It is **not** installed in the cmbagent-lg venv (its old langchain pins
conflict with the modern stack), so those error out. Idea / methods / results /
paper (without cmbagent keywords) do not need it.
