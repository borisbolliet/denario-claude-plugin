# Denario Assistant (Claude Code plugin)

Specialized [Claude Code](https://code.claude.com) assistance for driving the
[Denario](https://denario.readthedocs.io) multi-agent research assistant **over
MCP** — the end-to-end pipeline (idea → literature → methods → results →
evaluate/iterate → paper → classify/publish) and the underlying `cmbagent_lg`
analysis engine. This is the Claude-Code-native replacement for the OpenClaw
gateway that fronts each Denario "scientist": the skills carry the same workflow
knowledge and operating conventions, and the plugin bundles the MCP servers.

## What you get

- **`/denario:explain`** — passive knowledge skill: the two MCP servers (`denario`, `cmbagent_lg`), the pipeline stages and which tool runs each, the `params.yaml` control surface (per-role/multi-provider models, `max_n_steps`, the VLM image-reviewer), and crash-recoverable restart. Auto-loads when the conversation is about Denario, `denario_results`/`denario_idea`/…, `cmbagent_lg`, `params.yaml` analysis models, or `restart_at_step`.
- **`/denario:conventions`** — passive operating-rules skill: stage discipline (one stage per turn, read-don't-assume), where logs/outputs land, the **privacy + git/publish** rules (private by default, confirm before going public), and the **evaluate → iterate** loop. The behavioral layer the autonomous scientist got from its `SOUL.md`/`AGENTS.md`.
- **`/denario:run-pipeline <project_dir> [data description] [--literature --vlm --iterate=K --no-citations --publish]`** — runs the pipeline end-to-end through the denario MCP tools, configured from `params.yaml`; reports a concise summary. Default run is idea → methods → results → paper (citations **on** by default); literature, iteration, publish, etc. are opt-in flags.

## Prerequisite: the MCP servers (bundled)

The plugin **auto-registers** both MCP servers (`denario`, `cmbagent_lg`) via
`plugins/denario/.mcp.json` — they start when the plugin is enabled. You only
need to point them at your environment with two env vars (the servers ship with
Denario, in `denario/mcp_servers/`):

```bash
# the python that has cmbagent_lg + Denario + modern langchain (the py312-cmbagent-lg venv)
export DENARIO_MCP_PYTHON=/Users/boris/pyvenvs/py312-cmbagent-lg/bin/python
# the directory containing denario_server.py / cmbagent_lg_server.py
export DENARIO_MCP_DIR=/Users/boris/GitHub/Denario/denario/mcp_servers
```

Export them where Claude Code can see them (your shell profile, or the project
`.env`) before launching. The servers self-load `GOOGLE_API_KEY` from
`cmbagent_lg/.env`; add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` there or export
them too (stdio servers inherit Claude Code's environment).

Prefer to register them yourself instead? You can still do it manually and skip
the env vars:

```bash
LGPY=$DENARIO_MCP_PYTHON; DEN=$DENARIO_MCP_DIR
claude mcp add denario     -s user -- $LGPY $DEN/denario_server.py
claude mcp add cmbagent_lg -s user -- $LGPY $DEN/cmbagent_lg_server.py
```

See `/denario:explain` → reference.md for keys, the venv, and gotchas.

## Install (the plugin)

Local testing (no marketplace needed):
```bash
claude --plugin-dir ~/GitHub/denario-claude-plugin
```

From a marketplace (once published):
```
/plugin marketplace add borisbolliet/denario-claude-plugin
/plugin install denario@denario-claude-plugin
```

## Try it

```
/denario:explain
How do I configure a multi-provider results run and turn on the image reviewer?

/denario:run-pipeline ~/Desktop/sho-study "A 1D damped harmonic oscillator: study amplitude/energy decay vs damping."
```

## Layout

```
.claude-plugin/marketplace.json
plugins/denario/
  .claude-plugin/plugin.json
  .mcp.json             # bundles the denario + cmbagent_lg MCP servers (env-var configured)
  skills/
    explain/
      SKILL.md          # main knowledge skill (how to use the Denario MCP)
      reference.md      # tool signatures, full params.yaml schema, registration
    conventions/
      SKILL.md          # operating rules: privacy/git/publish, paths, iterate loop
    run-pipeline/
      SKILL.md          # end-to-end pipeline over MCP (+literature/iterate/classify/publish)
```

## Notes

- **MCP-first.** Unlike the cobaya plugin (CLI via Bash), Denario is driven through MCP tools (`mcp__denario__*`, `mcp__cmbagent_lg__*`). The plugin bundles both servers in `.mcp.json` (configure with `DENARIO_MCP_PYTHON` / `DENARIO_MCP_DIR`); the `run-pipeline` skill pre-approves the pipeline tools in `allowed-tools`.
- **`denario_results` is long and synchronous**; for non-blocking runs use `cmbagent_lg_execute` + `cmbagent_lg_status`.
- **Legacy stages.** `denario_eda` and the cmbagent-keyword paper path need the old `cmbagent` package, which is not in the cmbagent-lg venv — they're out of scope here.

## License

MIT
