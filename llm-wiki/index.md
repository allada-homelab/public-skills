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
* [PreToolUse guards each recompute the bundle path — relocate one, the floor fails open](./guard-bundle-path-coupling.md) — secret_guard and doctor_guard independently derive the bundle root; changing where the bundle lives without updating both silently disarms the auto-mode safety floor.
* [Registering a skill in the public-skills marketplace](./marketplace-skill-registration.md) — How to add a standalone skill to this marketplace — the manifest registers plugins (not skills directly), so a skill ships inside a plugin under plugins/<name>/skills/.
* [Repo ingestion — orchestrated multi-agent bootstrap](./repo-ingestion-architecture.md) — How /llm-wiki:ingest bootstraps a wiki from an existing repo — an orchestrator command fans out read-only Sonnet wiki-explorer subagents that return concept proposals, then writes one Doctor-gated autonomous batch.
* [Secret-scan entropy gate excludes path/URL separators](./secret-scan-entropy-gate.md) — Why TOKEN_RE matches only contiguous opaque alnum runs — paths, URLs, and slugs were the dominant false-positive source that made the blocking secret guard deny legitimate wiki captures.
