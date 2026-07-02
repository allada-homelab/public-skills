# Directory Update Log

## 2026-06-29

* **Update**: Refined [Where llm-wiki's value concentrates — knowledge the code can't tell you](./llm-wiki-value-on-multihop-navigation.md) after the gotcha-recall experiment.

## 2026-06-28

* **Creation**: Added [llm-wiki value shows on multi-hop navigation, not single-hop grep lookups](./llm-wiki-value-on-multihop-navigation.md) from the first optimizer run.
* **Creation**: Added [Retrieval is agentic-read-markdown — llm-wiki has no search engine](./retrieval-is-agentic-read-markdown.md).
* **Update**: Refined [Repo ingestion — orchestrated multi-agent bootstrap](./repo-ingestion-architecture.md) and [Reading is trust-but-verify — the consult-then-confirm loop](./trust-but-verify-loop.md) for the always-auto surface.
* **Update**: Refined [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md): collapsed modes, five hook events, background subagents.
* **Update**: Refined [OKF Doctor — strict-producer rule set](./doctor-rule-set.md): R5 removed; capture-upsert + apply engine.

## 2026-06-27

* **Creation**: Added [Post-compaction re-injection is a SessionStart-on-compact job, not PreCompact](./post-compaction-reinjection.md).
* **Creation**: Added [Reading is trust-but-verify — the consult-then-confirm loop](./trust-but-verify-loop.md).

## 2026-06-25

* **Creation**: Added [Registering a skill in the public-skills marketplace](./marketplace-skill-registration.md).

## 2026-06-17

* **Creation**: Added [Secret-scan entropy gate excludes path/URL separators](./secret-scan-entropy-gate.md).

## 2026-06-15

* **Creation**: Added [Repo ingestion — orchestrated multi-agent bootstrap](./repo-ingestion-architecture.md).
* **Creation**: Added [Plugin versioning — unpinned for git-SHA auto-update](./plugin-versioning.md).
* **Update**: Corrected the autonomy concept's description ("five wired hook events" → "six") and regenerated the index.
* **Update**: Refined [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md): UserPromptSubmit is now a once-per-session consult nudge (read-loop forcing function), not a per-turn capture nudge.
* **Update**: Refined [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) to document R5 (lonely-subdir) and the flat-first nesting policy.
* **Update**: Refined [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md): the Stop hook now fires only on turns that changed real code (PostToolUse `.llm-wiki/capture-pending` marker gate), not every turn.
* **Update**: Refined [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md) to add the Stop end-of-turn capture hook (six events).

## 2026-06-14

* **Creation**: Added [Phase 3 autonomy — hook-driven, auto-default with a guard floor](./phase-3-autonomy-architecture.md).
* **Update**: Refined [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) to document R4 link-health and the Phase 2 bundle_ops engine.
* **Creation**: Added [OKF Doctor — strict-producer rule set](./doctor-rule-set.md).
* **Initialization**: Bundle created.
