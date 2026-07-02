---
okf_version: "0.1"
---
# llm-wiki

Knowledge bundle for the `public-skills` repo. Concepts are added with `/llm-wiki:capture`
and read back with `/llm-wiki:query`.

## Concepts

* [A plugin can't declare a host-tool dependency (Workflow, etc.) — guard it with a fail-loud runtime precondition](./host-tool-dependency-not-declarable.md) — plugin.json and .mcp.json have no field to require a host-provided tool like the Workflow orchestration engine, so a plugin whose core path invokes one must check availability at runtime and stop loudly if it's absent — otherwise the command silently no-ops and the whole plugin looks inert.
* [A toggleable plugin hook ships as a disabled .example.json, not a commented-out hook](./disabled-hook-ships-as-example-file.md) — hooks.json is strict JSON (no comments) and a plugin's live hooks.json loads wholesale, so a hook you want present-but-off can't be commented out — ship it as a separate hooks/<name>.example.json plus its script, enabled by copying to hooks.json (dropping the _comment key) and running /reload-plugins.
* [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md) — How llm-wiki autonomy works — five deterministic hook events, always-on auto (no modes), a PreToolUse guard floor, and background Sonnet subagents that persist and validate.
* [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) — The conformance rules doctor.py enforces (R1/R2/R3a–c plus R4 link-health), its strict/lenient modes, and exit codes.
* [Plugin versioning — unpinned for git-SHA auto-update](./plugin-versioning.md) — Why plugin.json omits the version field — Claude Code falls back to the git commit SHA, so every commit auto-updates installed users during active development.
* [Post-compaction re-injection is a SessionStart-on-compact job, not PreCompact](./post-compaction-reinjection.md) — To re-inject wiki context after a compaction, branch the SessionStart hook on source=="compact" — a PreCompact hook is the wrong tool (its additionalContext may not survive compaction).
* [Reading is trust-but-verify — the consult-then-confirm loop](./trust-but-verify-loop.md) — Trust a wiki finding on its face, but cheaply confirm load-bearing claims against current state via a ## Verify anchor + freshness gate, with background self-healing verification.
* [Registering a skill in the public-skills marketplace](./marketplace-skill-registration.md) — How to add a standalone skill to this marketplace — the manifest registers plugins (not skills directly), so a skill ships inside a plugin under plugins/<name>/skills/.
* [Repo ingestion — orchestrated multi-agent bootstrap](./repo-ingestion-architecture.md) — How /llm-wiki:ingest bootstraps a wiki from an existing repo — an orchestrator command fans out read-only Sonnet wiki-explorer subagents that return concept proposals, then writes one Doctor-gated autonomous batch.
* [Retrieval is agentic-read-markdown — llm-wiki has no search engine](./retrieval-is-agentic-read-markdown.md) — llm-wiki has no embeddings, vector store, chunking, top-k, or reranking — retrieval is an agent grepping then reading index.md and following ./ links, so retrieval quality is tuned via the read prompt and index.md descriptions, not RAG hyperparameters.
* [Secret-scan entropy gate excludes path/URL separators](./secret-scan-entropy-gate.md) — Why TOKEN_RE matches only contiguous opaque alnum runs — paths, URLs, and slugs were the dominant false-positive source that made the blocking secret guard deny legitimate wiki captures.
* [Where llm-wiki's value concentrates — knowledge the code can't tell you](./llm-wiki-value-on-multihop-navigation.md) — Optimizer experiments show the wiki's measurable value concentrates at the intersection of a weaker agent, knowledge not recoverable from the code (subtle runtime root causes and the why), and answer completeness — it pays off for what the code cannot tell you, not for file-finding or fixes already committed in the repo.
