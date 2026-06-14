# llm-wiki — design docs

Planning and design for the `llm-wiki` plugin. Three documents, distinct purposes, read in order:

| Doc | Purpose | Audience |
|---|---|---|
| [PRODUCT_PLAN.md](./PRODUCT_PLAN.md) | What the plugin is and how it behaves — vision, personas, capabilities, autonomy model. Product, not implementation. | product |
| [PHASE_PLAN.md](./PHASE_PLAN.md) | The 4-phase roadmap and the capability → Claude Code primitive mapping. Authoritative on phasing/sequencing. | architecture |
| [PHASE_1_TECH_PLAN.md](./PHASE_1_TECH_PLAN.md) | The buildable spec for Phase 1 (MVP): manifests, command contracts, the Doctor, fixtures. | implementation |

Where they disagree, the later/more-specific doc wins (PHASE_PLAN over PRODUCT_PLAN on phasing;
PHASE_1_TECH_PLAN over both on Phase 1 specifics).

[`reference/`](./reference/) holds the source material these plans are built on: the distilled OKF
v0.1 spec (`okf_spec.md` — what the Doctor enforces), the OKF announcement (`okf_blog.md`) and repo
links (`okf_repo.md`), and the Claude Code plugin-system reference (`claude_code_plugin_system.md`).

## Status (2026-06-14)

- **Phase 1 — Prove the Loop (MVP): ✅ shipped & dogfooded.** Marketplace + plugin, the
  `llm-wiki:wiki` skill, five commands (init/capture/explore/query/conform), and the deterministic
  Doctor + report-only secret scanner. Test corpus green (`pass=10 fail=0 skip=1`). Dogfooded on
  this repo — see [`/llm-wiki`](../../llm-wiki/). Only the GitHub-render check is "inferred,
  not observed."
- **Phase 2 — Make It Durable: planned.** refine / prune / reorganize + automated `index.md`/`log.md`
  + reorg link-health diff.
- **Phase 3 — Autonomous (hooks, modes, self-improve)** and **Phase 4 — Interoperate** — planned.

Backlog ideas (loop-based curation, a dedicated cheaper curation model, the blocking secret hook)
are recorded in [PRODUCT_PLAN.md](./PRODUCT_PLAN.md#future-ideas--backlog-not-committed-to-mvpv1)
and PHASE_PLAN locked decisions.
