---
description: Answer a question grounded in the llm-wiki, with citations and a gap flag.
argument-hint: "<question> [--bundle <path>]"
allowed-tools: Glob, Grep, Read, Write
---

You are running `/llm-wiki:query`. Answer the user's question **only** from concepts you actually read,
with citations. Use the `wiki` skill for the format. Read-only except an optional, confirm-gated
consultation-counter write.

Arguments: `$ARGUMENTS` is the question (**required** — if empty, ask for it; never guess). It may also
carry `--bundle <path>`.

Steps:

1. **Resolve the bundle root** (`--bundle`, else walk up from `${CLAUDE_PROJECT_DIR}`). None →
   "No OKF bundle here. Run `/llm-wiki:init` first."
2. **Find entry points.** Grep key terms from the question and read the root `index.md`. Traverse
   minimally, following only cross-links that bear on the question. A concept "counts" only when you
   actually `Read` its body (index files don't count).
3. **Answer from read content only.** Ground every claim in a concept; cite each by its bundle-relative
   path / title. End with a `Sources:` list. Do **not** fabricate or fill gaps from general knowledge.
4. **Gap flag (required).** If no concept answers, say "The wiki does not contain an answer to this,"
   and emit a structured line:
   `GAP: <question> — no concept covers <topic>. Consider /llm-wiki:capture to add it.`
   A query can be partly answered and partly a gap — report both. Phase 1 only *reports* gaps.
5. **Consultation counter (confirm-first).** As in `/llm-wiki:explore`: propose incrementing the
   consulted concepts' counts in `<bundle-root>/.llm-wiki/consultations.json` and write only on
   approval. Corrupt/missing file → treat as `{}`; never let counter bookkeeping break the answer.
