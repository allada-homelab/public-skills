---
type: gotcha
title: A plugin can't declare a host-tool dependency (Workflow, etc.) — guard it with a fail-loud runtime precondition
description: plugin.json and .mcp.json have no field to require a host-provided tool like the Workflow orchestration engine, so a plugin whose core path invokes one must check availability at runtime and stop loudly if it's absent — otherwise the command silently no-ops and the whole plugin looks inert.
tags:
  - plugin
  - hooks
  - convention
  - gotcha
  - orchestration
generated: { by: llm-wiki/unknown, at: 2026-07-02 }
verified: { by: llm-wiki/unknown, at: 2026-07-02 }
---

# Host-tool dependency → fail-loud runtime precondition, not a manifest field

A Claude Code plugin manifest (`plugin.json`) and `.mcp.json` can declare MCP servers and metadata, but there is **no field to require a host-provided tool** — e.g. the `Workflow` orchestration engine, or any capability gated by the session/host rather than shipped by the plugin. So if a plugin's core path invokes such a tool and it isn't present in the session, the command **silently no-ops** and the plugin appears inert with no error.

**Convention (used by `get-shit-done`, whose fan-out depends on `Workflow`):** make the host-tool a **runtime precondition** — the command's first steps state the requirement and, if the tool is unavailable, say so plainly and **stop** rather than proceeding. State it as a hard prerequisite in the README too. This turns a silent no-op into a fail-loud, matching the "fail fast and loud" rule.

The same shape applies to optional external *agents* (`agent({agentType})` against an uninstalled plugin agent fails): use them only when present and fall back to the default worker otherwise.

## Verify

- `plugins/get-shit-done/commands/run.md` — the **Precondition** line ("if [Workflow] is not available in this session, say so plainly and stop — never silently no-op") ahead of the numbered steps.
- `plugins/get-shit-done/README.md` — the Requirements bullet stating the `Workflow` tool is required (and optional reviewer/research agents are not).
