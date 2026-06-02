# Denario Assistant (Claude Code plugin)

Specialized [Claude Code](https://code.claude.com) assistance for driving the
[Denario](https://denario.readthedocs.io) multi-agent research assistant **over
MCP** — the end-to-end pipeline (idea → methods → results → paper) and the
underlying `cmbagent_lg` analysis engine.

## What you get

- **`/denario:explain`** — passive knowledge skill: the two MCP servers (`denario`, `cmbagent_lg`), the pipeline stages and which tool runs each, the `params.yaml` control surface (per-role/multi-provider models, `max_n_steps`, the VLM image-reviewer), and crash-recoverable restart. Auto-loads when the conversation is about Denario, `denario_results`/`denario_idea`/…, `cmbagent_lg`, `params.yaml` analysis models, or `restart_at_step`.
- **`/denario:run-pipeline <project_dir> [data description]`** — runs the full pipeline end-to-end through the denario MCP tools (lay out the project → idea → methods → results → paper), configured from `params.yaml`; reports a concise summary.

## Prerequisite: the MCP servers

This plugin tells Claude how to *use* the Denario MCP tools; you must have the two
servers registered (they ship with Denario, in `denario/mcp_servers/`):

```bash
LGPY=/Users/boris/pyvenvs/py312-cmbagent-lg/bin/python
DEN=/Users/boris/GitHub/Denario/denario/mcp_servers
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
  skills/
    explain/
      SKILL.md          # main knowledge skill (how to use the Denario MCP)
      reference.md      # tool signatures, full params.yaml schema, registration
    run-pipeline/
      SKILL.md          # end-to-end pipeline over MCP
```

## Notes

- **MCP-first.** Unlike the cobaya plugin (CLI via Bash), Denario is driven through MCP tools (`mcp__denario__*`, `mcp__cmbagent_lg__*`). The `run-pipeline` skill pre-approves the pipeline tools in `allowed-tools`.
- **`denario_results` is long and synchronous**; for non-blocking runs use `cmbagent_lg_execute` + `cmbagent_lg_status`.
- **Legacy stages.** `denario_eda` and the cmbagent-keyword paper path need the old `cmbagent` package, which is not in the cmbagent-lg venv — they're out of scope here.

## License

MIT
