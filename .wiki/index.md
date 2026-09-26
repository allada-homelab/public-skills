---
okf_version: "0.2"
---

# Gotcha

* [A phantom or noisy llm-wiki Stop nudge comes from Claude Code hook runtime facts](./stop-nudge-hook-runtime-facts.md) - Hooks fire for subagent tool calls with the parent session_id, and a blocking Stop reason always renders as "Stop hook error"; scope write markers per session and in-project, keep the reason short.
* [Post-compaction re-injection is a SessionStart-on-compact job, not PreCompact](./post-compaction-reinjection.md) - To re-inject wiki context after compaction, branch the SessionStart hook on source compact; a PreCompact hook is the wrong tool because its output may be folded into the compaction summary.

# Decision

* [Evaluate the wiki on knowledge the code can't tell you, with a weaker agent](./wiki-value-is-knowledge-not-in-code.md) - Wiki-vs-ablated runs showed uplift only for a weaker agent, for runtime knowledge and the why, and for answer completeness; benchmark there, not on file-finding a strong agent already greps.
* [get-shit-done and minimalist-code-review are frozen copies here](./frozen-plugins-maintained-upstream.md) - Change get-shit-done and minimalist-code-review in agent-harness-marketplace, not here; the copies in this repo are frozen, and nothing inside their plugin dirs says so.
* [Plugin versioning — pinned; every user-visible change requires a version bump](./plugin-versioning.md) - plugin.json pins version, so installed users get an update only when it is bumped; a push without a bump strands them on the stale cache while /plugin reports already at the latest version.
* [wiki-capturer is deliberately outside the read-path gate](./scribe-exempt-from-read-path-gate.md) - Leave wiki-capturer out of hook_pre_read's _PROTECTED_AGENTS; it must Read its own /tmp request and prepared files, which the gate's outside-the-project rule would deny.

# Runbook

* [llm-wiki gates: unittest is the real suite, drift_check is red at HEAD](./llm-wiki-test-gates.md) - Gate llm-wiki changes on its unittest suite, which CLAUDE.md omits; drift_check.sh already fails 19 checks at HEAD, so compare its FAIL count before and after instead of expecting PASS.
