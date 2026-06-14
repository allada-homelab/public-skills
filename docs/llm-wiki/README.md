# llm-wiki — design docs

Planning and design for the `llm-wiki` plugin. Three documents, distinct purposes, read in order:

| Doc | Purpose | Audience |
|---|---|---|
| [PRODUCT_PLAN.md](./planning/PRODUCT_PLAN.md) | What the plugin is and how it behaves — vision, personas, capabilities, autonomy model. Product, not implementation. | product |
| [PHASE_PLAN.md](./planning/PHASE_PLAN.md) | The 4-phase roadmap and the capability → Claude Code primitive mapping. Authoritative on phasing/sequencing. | architecture |
| [phase-1-tech-plan.md](./phases/phase-1-tech-plan.md) | The buildable spec for Phase 1 (MVP): manifests, command contracts, the Doctor, fixtures. | implementation |
| [phase-2-tech-plan.md](./phases/phase-2-tech-plan.md) | The buildable spec for Phase 2 (durability): the `bundle_ops` engine, Doctor R4, refine/prune/reorganize. | implementation |
| [TRIAL_BRIEF.md](./TRIAL_BRIEF.md) | How to trial the plugin in another repo and bring findings back to scope later phases. | dogfooding |

Where they disagree, the later/more-specific doc wins (PHASE_PLAN over PRODUCT_PLAN on phasing;
a phase tech plan over both on that phase's specifics).

[`reference/`](./reference/) holds the source material these plans are built on: the distilled OKF
v0.1 spec (`okf_spec.md` — what the Doctor enforces), the OKF announcement (`okf_blog.md`) and repo
links (`okf_repo.md`), and the Claude Code plugin-system reference (`claude_code_plugin_system.md`).

## Status (2026-06-14)

- **Phase 1 — Prove the Loop (MVP): ✅ shipped & dogfooded.** Marketplace + plugin, the
  `llm-wiki:wiki` skill, five commands (init/capture/explore/query/conform), and the deterministic
  Doctor + report-only secret scanner. Dogfooded on this repo — see [`/llm-wiki`](../../llm-wiki/).
  Only the GitHub-render check is "inferred, not observed."
- **Phase 2 — Make It Durable: ✅ shipped & dogfooded.** `refine` / `prune` / `reorganize` over the
  deterministic `bundle_ops` engine (index regeneration, `log.md` appends, link-preserving moves) and
  Doctor **R4 link-health** with a reorganize pre/post diff. Both corpora green (Doctor
  `pass=12 fail=0 skip=0`, engine golden `pass=12 fail=0`); the `reference/` reorganization was
  dogfooded on this repo's bundle with zero broken links.
- **Phase 3 — Autonomous (hooks, modes, self-improve)** and **Phase 4 — Interoperate** — planned.

Backlog ideas (loop-based curation, a dedicated cheaper curation model, the blocking secret hook)
are recorded in [PRODUCT_PLAN.md](./planning/PRODUCT_PLAN.md#future-ideas--backlog-not-committed-to-mvpv1)
and PHASE_PLAN locked decisions.
