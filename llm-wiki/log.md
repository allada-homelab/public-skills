# Directory Update Log

## 2026-06-15

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
