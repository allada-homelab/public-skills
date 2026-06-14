# Claude Code Plugin System — Composition Reference

> Reference notes compiled 2026-06-14 from the installed `plugin-dev` skills
> (`plugin-structure`, `skill-development`, `mcp-integration`, `command-development`,
> `hook-development`, `agent-development`) and official Claude Code docs. Confirm exact
> field names against current docs before relying on them.

## Marketplace Repo Structure

A marketplace is a git repository with a `.claude-plugin/marketplace.json` at its root.

**`marketplace.json` top-level fields:**
```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "marketplace-name",
  "description": "...",
  "owner": { "name": "...", "email": "..." },
  "plugins": [ ... ]
}
```

**Per-plugin entry fields** (inside `"plugins": []`):
- `name` (required) — kebab-case identifier
- `description` (required) — shown in discovery UI
- `author` (optional) — `{ "name", "email", "url" }`
- `category` (optional) — e.g. `"development"`, `"productivity"`, `"security"`
- `homepage` (optional) — docs URL
- `keywords` / `tags` (optional)
- `source` (required) — one of four forms:

  | Form | When to use | Example |
  |------|-------------|---------|
  | **Inline path** | Plugin lives inside the marketplace repo | `"source": "./plugins/my-plugin"` |
  | **`git-subdir`** | Plugin is a subdirectory of another repo | `{ "source": "git-subdir", "url": "...", "path": "plugins/foo", "ref": "main", "sha": "abc..." }` |
  | **`url`** | Plugin is the root of an external repo | `{ "source": "url", "url": "https://github.com/org/repo.git", "sha": "abc..." }` |
  | **`github`** | GitHub shorthand | `{ "source": "github", "repo": "org/repo", "commit": "...", "sha": "..." }` |

  The `sha` field pins the exact commit. `ref` is the branch/tag for human readability; `sha` is authoritative.

## Plugin Structure

The `plugin.json` manifest lives at **`.claude-plugin/plugin.json`** — never at the plugin root. All component directories (`commands/`, `agents/`, `skills/`, `hooks/`) live at the **plugin root**, not inside `.claude-plugin/`.

**Minimal `plugin.json`:**
```json
{ "name": "plugin-name" }
```

**Full `plugin.json` fields:**
```json
{
  "name": "plugin-name",           // required, kebab-case
  "version": "1.0.0",              // semver
  "description": "...",
  "author": { "name": "...", "email": "...", "url": "..." },
  "homepage": "...",
  "repository": "...",
  "license": "MIT",
  "keywords": ["tag1"],
  "commands": "./custom-commands",  // supplements default, not replaces
  "agents": ["./agents", "./more-agents"],  // arrays supported
  "hooks": "./config/hooks.json",   // custom hooks file path
  "mcpServers": "./.mcp.json"       // or inline mcpServers object
}
```

**Conventional directory layout:**
```
plugin-name/
├── .claude-plugin/
│   └── plugin.json          # manifest
├── commands/                # *.md slash command files
├── agents/                  # *.md agent files
├── skills/
│   └── skill-name/
│       ├── SKILL.md         # required; frontmatter: name, description, version
│       ├── references/      # docs loaded on-demand
│       ├── examples/
│       └── scripts/
├── hooks/
│   ├── hooks.json           # plugin hook config (wrapped format)
│   └── scripts/
├── .mcp.json                # MCP server definitions (recommended)
└── scripts/                 # shared utilities
```

## MCP Server Declaration

Two places to declare MCP servers in a plugin:

**Preferred: `.mcp.json` at plugin root**
```json
{
  "server-name": {
    "command": "${CLAUDE_PLUGIN_ROOT}/servers/my-server",
    "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
    "env": { "API_KEY": "${API_KEY}" }
  }
}
```

**Alternative: inline `mcpServers` in `plugin.json`**
```json
{
  "name": "my-plugin",
  "mcpServers": {
    "server-name": { "command": "...", "args": [...] }
  }
}
```

**Server types:**
| Type | Config key | Use for |
|------|-----------|---------|
| stdio | `command` + `args` + optional `env` | Local processes (node, python, npx) |
| SSE | `type: "sse"`, `url` | Hosted services with OAuth |
| HTTP | `type: "http"`, `url`, `headers` | REST APIs with token auth |
| WebSocket | `type: "ws"`, `url`, `headers` | Real-time bidirectional |

**`${CLAUDE_PLUGIN_ROOT}`** expands to the plugin's absolute installation path. Use it in every command/path reference inside hook scripts and MCP configs. The shell environment also exposes `$CLAUDE_PROJECT_DIR` and `$CLAUDE_ENV_FILE` (SessionStart only).

**MCP tool naming:** tools are automatically prefixed as `mcp__plugin_<plugin-name>_<server-name>__<tool-name>`.

## Decision Boundaries: Which Capability Type to Use

### SKILL
- **Invocation:** Model-driven. Claude reads the `description` frontmatter and autonomously loads the skill body when the task matches.
- **Strengths:** Zero invocation friction; progressive disclosure (metadata → body → references → scripts); bundles domain knowledge, reusable scripts, reference docs, and asset templates in one package.
- **Limits:** Cannot directly run side effects or make network calls; cannot be invoked explicitly by name in a command; activates on context match only.
- **Use when:** Teaching Claude a specialized workflow or domain (e.g., "how to write DuckDB queries", "PDF rotation script", "company API schema").

### SLASH COMMAND
- **Invocation:** User-typed (`/command-name [args]`). Can also be invoked programmatically via the `SlashCommand` tool (unless `disable-model-invocation: true`).
- **Strengths:** Repeatable, user-initiated workflows; supports `$ARGUMENTS`, `$1`/`$2` positional args, `@file` references, and inline bash via `` !`cmd` ``; can restrict tools via `allowed-tools`.
- **Limits:** Requires explicit user invocation; no autonomous triggering.
- **Use when:** Standardizing a workflow the user will explicitly kick off (e.g., `/review-pr`, `/deploy staging`).

### AGENT (Subagent)
- **Invocation:** Model-driven via description + examples, or explicitly launched via the `Task` tool. Runs as an isolated subprocess.
- **Strengths:** Autonomous multi-step work; isolated context; can be assigned specific `tools` (least-privilege); `model`, `color` customizable; the `description` field with `<example>` blocks controls triggering.
- **Limits:** Cannot hot-swap during a session; requires a well-crafted description to trigger correctly.
- **Use when:** Long-running, self-contained sub-tasks that benefit from isolation (e.g., `code-reviewer`, `test-generator`), or when you want Claude to delegate automatically based on task type.

### HOOK
- **Invocation:** Event-triggered automatically by the Claude Code runtime. Events: `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `UserPromptSubmit`, `SessionStart`, `SessionEnd`, `PreCompact`, `Notification`.
- **Hook types:** `"type": "prompt"` (LLM reasoning, supports `PreToolUse`/`Stop`/etc.) or `"type": "command"` (bash, deterministic).
- **Plugin format** (`hooks/hooks.json`) wraps events in a `"hooks"` key; user settings format puts events at the top level directly.
- **Strengths:** Invisible to users; enforces policies globally; can block, modify, or augment tool calls; `PreToolUse` can return `permissionDecision: allow|deny|ask` and `updatedInput`.
- **Limits:** Loaded at session start — changes require a restart. All matching hooks run in parallel (no guaranteed order). Timeout defaults: commands 60s, prompts 30s.
- **Use when:** Enforcing guardrails, loading context at startup, validating completeness before stop, or logging/auditing tool usage.

### MCP SERVER
- **Invocation:** Tools exposed by the server appear as first-class callable tools (prefixed `mcp__plugin_...__...`); Claude calls them the same way it calls built-in tools.
- **Strengths:** Exposes external service APIs (databases, SaaS, file systems) as structured tools; handles auth (OAuth for SSE, tokens for HTTP); supports 10+ related tools from one server; integrates deeply with the permission system.
- **Limits:** Requires a running process or network endpoint; heavier setup than a skill; tools must be explicitly allowed in command frontmatter if not already permitted.
- **Use when:** You need real external state (read/write a database, call an API, control a browser), especially when 5+ related operations belong together.

## Notes / Caveats (flagged by research)

- The `hooks/hooks.json` plugin format requires a `{ "hooks": { ... } }` wrapper — this differs from the user `settings.json` format, which puts events at the top level directly. Mixing them up is a common error.
- The `SKILL.md` `description` field should use third-person ("This skill should be used when..."), not second-person — intentional for the model-as-reader pattern.
- The `source` field in `marketplace.json` supports four distinct referencing schemes (`url`, `git-subdir`, `github`, inline `./path`) — richer than commonly documented.
