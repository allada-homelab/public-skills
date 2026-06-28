---
type: Architecture
title: Retrieval is agentic-read-markdown — llm-wiki has no search engine
description: llm-wiki has no embeddings, vector store, chunking, top-k, or reranking — retrieval is an agent grepping then reading index.md and following ./ links, so retrieval quality is tuned via the read prompt and index.md descriptions, not RAG hyperparameters.
tags:
  - retrieval
  - architecture
  - query
verified: 2026-06-28
---
# Retrieval is agentic-read-markdown — llm-wiki has no search engine

llm-wiki has **no retrieval engine**. There is no embedding model, vector store, chunking, top-k,
reranking, or similarity scoring anywhere in the plugin. "Retrieval" is entirely **agentic read of
markdown**: an LLM agent greps the repo, reads the root `index.md`, follows the `./` cross-links that
bear on the question, and reads whole concept files. The "index" is literally `index.md` — a markdown
bullet list (regenerated from each concept's frontmatter by `bundle_ops index`), **not** a search
index.

The read path (`commands/query.md`): grep key terms from the question → read the root `index.md` →
traverse minimally, following only on-topic cross-links → answer **only** from concept bodies actually
`Read` (index files don't count), citing each by path → emit a `GAP:` line when no concept covers it.
`SessionStart` preloads the whole `index.md` body into context; nothing else is "indexed".

## Why it matters

Any work that assumes RAG hyperparameters — picking an embedding model, tuning chunk size, setting
top-k, adding a reranker — is **misdirected**, because none of those exist or apply. The real tunable
surface for retrieval quality is:

- the **read/consult prompt** (`query.md` traversal + grounding policy, the `SKILL.md` consult loop),
- the **`index.md` description quality + frontmatter `tags`** — the only things preloaded and shown in
  browse, so weak descriptions leave the agent unable to decide what to open,
- the **preload behavior** (the full index enters context, a real scaling lever as the bundle grows).

Tune the prompt and the descriptions, not a retrieval engine that isn't there.

## Verify
- run: `grep -rniE 'embed|vector|faiss|rerank|top_k|topk|top-k|similarity|cosine|chunk' plugins/llm-wiki/ | grep -viE 'image embed|embedded newline'` — expected: no retrieval-engine matches (only incidental false positives)
- plugins/llm-wiki/commands/query.md — the read path is grep + read index.md + follow ./ links + read concept bodies, with no search or embedding step

## Related
- See [Reading is trust-but-verify — the consult-then-confirm loop](./trust-but-verify-loop.md) — the read ethos this agentic navigation enables.
- See [Repo ingestion — orchestrated multi-agent bootstrap](./repo-ingestion-architecture.md) — how the concepts this path reads get created.
