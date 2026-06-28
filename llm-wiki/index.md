---
okf_version: "0.1"
---
# llm-wiki

Knowledge bundle for the `public-skills` repo. Concepts are added with `/llm-wiki:capture`
and read back with `/llm-wiki:query`.

## Concepts

* [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md) — How llm-wiki autonomy works — five deterministic hook events, always-on auto (no modes), a PreToolUse guard floor, and background Sonnet subagents that persist and validate.
* [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) — The conformance rules doctor.py enforces (R1/R2/R3a–c plus R4 link-health), its strict/lenient modes, and exit codes.
* [Plugin versioning — unpinned for git-SHA auto-update](./plugin-versioning.md) — Why plugin.json omits the version field — Claude Code falls back to the git commit SHA, so every commit auto-updates installed users during active development.
* [Reading is trust-but-verify — the consult-then-confirm loop](./trust-but-verify-loop.md) — Trust a wiki finding on its face, but cheaply confirm load-bearing claims against current state via a ## Verify anchor + freshness gate, with background self-healing verification.
* [Registering a skill in the public-skills marketplace](./marketplace-skill-registration.md) — How to add a standalone skill to this marketplace — the manifest registers plugins (not skills directly), so a skill ships inside a plugin under plugins/<name>/skills/.
* [Repo ingestion — orchestrated multi-agent bootstrap](./repo-ingestion-architecture.md) — How /llm-wiki:ingest bootstraps a wiki from an existing repo — an orchestrator command fans out read-only Sonnet wiki-explorer subagents that return concept proposals, then writes one Doctor-gated autonomous batch.
* [Retrieval is agentic-read-markdown — llm-wiki has no search engine](./retrieval-is-agentic-read-markdown.md) — llm-wiki has no embeddings, vector store, chunking, top-k, or reranking — retrieval is an agent grepping then reading index.md and following ./ links, so retrieval quality is tuned via the read prompt and index.md descriptions, not RAG hyperparameters.
* [Secret-scan entropy gate excludes path/URL separators](./secret-scan-entropy-gate.md) — Why TOKEN_RE matches only contiguous opaque alnum runs — paths, URLs, and slugs were the dominant false-positive source that made the blocking secret guard deny legitimate wiki captures.
