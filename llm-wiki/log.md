# Directory Update Log

## 2026-07-09

* **Update**: Removed the llm-wiki test-fixture corpora (Doctor/bundle_ops/hook fixtures) and pruned the three now-obsolete fixture-harness concepts.

## 2026-07-04

* **Update**: Updated [Capture marker is session-scoped](./capture-marker-is-project-scoped.md) — added the empirically verified fact that subagent tool calls carry the parent session's session_id, closing the design's one open assumption.
* **Update**: Auto-refined [PostToolUse fires for subagent tool calls and /tmp writes — broad markers self-arm](./posttooluse-fires-for-subagents-and-tmp.md) after verification.
* **Creation**: Captured Hook fixtures can't test age-based behavior — the harness's plain `cp -r` resets bundle mtimes, discovered while adding the stale-marker sweep fixtures.
* **Update**: Auto-refined [Post-compaction re-injection is a SessionStart-on-compact job, not PreCompact](./post-compaction-reinjection.md) after verification.
* **Update**: Updated [Capture marker is session-scoped](./capture-marker-is-project-scoped.md) — the project-scoped-marker gotcha was fixed by embedding the session_id in the marker filename (2026-07-04); concept now documents the fixed design and the remaining by-design deferral.
* **Creation**: Captured [Capture marker is project-scoped, not session-scoped](./capture-marker-is-project-scoped.md) — why the Stop nudge can fire on a pure-chat turn and why "Stop hook error" is not a crash.

## 2026-07-02

* **Update**: Refined [OKF Doctor — strict-producer rule set](./doctor-rule-set.md).
* **Update**: Auto-refined [OKF Doctor — strict-producer rule set](./doctor-rule-set.md) after verification.
* **Update**: Refined [Repo ingestion — orchestrated multi-agent bootstrap](./repo-ingestion-architecture.md).
* **Update**: Refined [Plugin versioning — unpinned for git-SHA auto-update](./plugin-versioning.md).
* **Update**: Refined [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md).
* **Update**: Refined [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md).
* **Creation**: Added Verify anchors should not assert exact fixture counts.
* **Update**: Auto-refined [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md) after verification.
* **Creation**: Added [PostToolUse fires for subagent tool calls and /tmp writes — broad markers self-arm](./posttooluse-fires-for-subagents-and-tmp.md).
* **Update**: Auto-refined [llm-wiki autonomy — zero-config always-auto with a guard floor](./phase-3-autonomy-architecture.md) after verification.
* **Creation**: Added ops fixture expect_err must not start with a dash.
* **Creation**: Added [apply commits by re-building on live, not copying the mirror](./apply-rebuilds-live-not-cp.md).
* **Creation**: Add gotcha: plugins can't declare host-tool dependencies in manifest — use fail-loud runtime precondition instead
* **Creation**: Capture gotcha: toggleable plugin hooks ship as disabled .example.json, not commented-out hooks.json entries

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
