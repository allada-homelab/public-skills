---
okf_version: "0.1"
---
# llm-wiki

Knowledge bundle for the `public-skills` repo. Concepts are added with `/llm-wiki:capture`
and read back with `/llm-wiki:explore` / `/llm-wiki:query`.

## Concepts

* [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) — The conformance rules doctor.py enforces (R1/R2/R3a–c, R4 link-health, R5 lonely-subdir), plus its modes and exit codes.
* [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) — How llm-wiki autonomy works — six wired hook events, a proactive-by-default mode, and the always-on PreToolUse guard floor that makes the default safe.
* [Plugin versioning — unpinned for git-SHA auto-update](./plugin-versioning.md) — Why plugin.json omits the version field — Claude Code falls back to the git commit SHA, so every commit auto-updates installed users during active development.
