# Tech plan — "consult, then confirm" ethos

**Status:** implemented — MVP + the ingest/wiki-explorer anchor wiring + the `/tend` freshness sweep · revised after a 4-lens review
**Goal — "trust but verify."** The wiki is a *somewhat-trusted summary* (curated, Doctor-gated,
cross-linked — a good starting point, not a guess) that doubles as a *fast index into current state*. The
posture is **high prior, cheap check**: the agent leans on a finding but, before *acting* on it, does a
**quick, targeted confirmation** that it still holds against current state (usually the code) — cheap
*because* the concept records where to look. This is deliberately **not** "treat the wiki as an unproven
hypothesis and re-derive it" — that framing pushes toward heavyweight re-investigation, the exact failure
mode the "lightweight" rule fights. Trust the summary; verify the spot it points to. (It is the CLAUDE.md
spirit — verify before claiming done — applied with an appropriately high prior on curated knowledge.)

## Decisions (locked, refined by review)

1. **Verification anchor = a body `## Verify` convention** (not a frontmatter key, not `resource:`).
   What makes the ethos work is anchor *quality*, so the bar is part of the decision:
   - **Free-form text, NOT a markdown link.** Write `scripts/doctor.py:parse_frontmatter`, not
     `[doctor.py](../../scripts/doctor.py)`. A real link pointing outside the bundle would trip the
     Doctor's R4 link-health with false broken-link warnings — the exact codebase-coupling Decision 1
     avoids.
   - **A *good* anchor is checkable:** a resolvable `file:symbol`, or a runnable
     `run: <grep/one-liner> — expected: <result>`. **Never** prose-only ("see the code"), **never** a
     bare `file:line` (line numbers rot on the first edit above them → false verdicts).
   - **Path convention:** repo-root-relative (`scripts/doctor.py`, `src/auth/token.go:verify`), resolved
     against `${CLAUDE_PROJECT_DIR}`.
   - Encouraged by authoring + surfaced by `/tend` (which flags *weak/prose-only* anchors, not just
     missing ones), but **NOT Doctor-enforced** (the Doctor is stdlib + codebase-agnostic; some concepts
     aren't code-verifiable).
2. **Confirm is three-state, and query FLAGS — it does not rewrite.** The review found `query.md` is
   read-only (`allowed-tools: Glob, Grep, Read, Write` — no Bash), so it *cannot* run the refine
   pipeline, and a silent rewrite-on-read would be a trust surprise. So:
   - Each load-bearing claim is labelled **confirmed** / **stale** / **couldn't-verify** (the third covers
     non-code concepts and anchors not resolvable in this workspace).
   - On **stale**, query emits a structured `STALE: <concept> — wiki says X; current state shows Y` line
     (parallel to its existing `GAP:` line) and proposes `/llm-wiki:refine <concept>`. The **refine runs
     on the refine surface**, which already has the gate, the tools, and is where re-derivation is
     legitimately in scope — **auto in an auto mode (`proactive`/`max`), confirm-first in `curated`**.
     *(This preserves Decision 2's original auto-on-stale behavior; it only relocates the executor out of
     the read path — query can't and shouldn't be a gated writer.)*
   - **Auto-refine fires only on a *divergent executable check*** (a `run:` anchor whose output
     contradicted the concept) — never on a prose-reading judgment, which is the path that would let a
     mis-read silently corrupt a correct concept. It is **capped one auto-refine per concept per session**
     (anti-thrash) and **surfaces one visible line** when it happens — the no-prose-recap rule is broken
     *for this case only*, because a silent correctness-mutation of human-curated knowledge is the one
     event that must surface. Non-code concepts are **confirm-exempt** (stamp "not code-verifiable; last
     confirmed `<timestamp>`"), never a refine trigger.

   **Correctness vs conformance:** the Doctor+secret gate makes the *write* safe (conformant, no secrets)
   — it does **not** verify the new content is *correct*. The correctness guards are the three above
   (executable-divergence-only, cap, surface), not the gate.
3. **Trust on face; verify in the background, gated by a cheap freshness check.** The main loop is
   **never blocked** on verification — this is what answers the "more work / slowness" objection.
   - **Use immediately.** A wiki finding is trusted on its face and used *now* (the somewhat-trusted-summary
     posture). No synchronous per-claim verification in the read path by default.
   - **Freshness gate (cheap, sync, deterministic).** Each concept records the commit/time it was last
     confirmed against (a `verified:` stamp or the anchored file's SHA). On read, compare the anchored
     file's last-change to it — a `git` check, no model. **Unchanged → trust, spawn nothing** (the common
     case, ~free). **Changed → verify.**
   - **Background verifier.** On a changed anchor, dispatch a background **`wiki-verifier`** subagent on a
     cheaper model (Sonnet) and **keep working**. It reads the anchor, returns confirm / stale+why, and on
     objective (`run:`) divergence self-heals via the gated refine (Decision 2's guards: executable-only,
     capped, surfaced); a prose "looks stale" is **reported, not auto-applied**.
   - **Hybrid escalation.** Verify **inline** (brief block) only when the changed claim is high-stakes for
     the action about to be taken, or the anchor is a quick `run:` one-liner (cheaper than spawning).
     Everything else goes background.
   - **Spawn is gated, not always-on.** Spawning a verifier per lookup regardless of change would launch a
     fleet of cheap-model agents re-confirming the unchanged majority. The git gate filters spawns to
     changed anchors; the verifier, when it runs, does the deep read+reason check the gate can't. (Flip to
     spawn-always only if catching non-git-visible drift — a concept wrong-when-written, or drift in a file
     the anchor didn't name — outweighs the token cost.)
   - **Lifecycle.** Cap + dedup verifiers per session (don't re-spawn for a concept already in flight);
     they die with the session — an unfinished verify just re-triggers next read; concurrent self-heals go
     through the existing one-at-a-time Doctor-gated apply.

   **The tradeoff, named:** background verification protects the *next* read and keeps the wiki
   self-healing over time; it does **not** retro-protect an action the main loop already took on the
   trusted-on-face value. The hybrid inline-escalation is the escape hatch for the rare act-now-high-stakes
   case. This optimizes *wiki freshness over time* + *fast main loop* over *this single answer's certainty*
   — the right trade for compounding knowledge reuse.

## The paired change (capture ⇄ read)

Read-time confirmation is only *cheap* if capture-time recorded a *good* anchor. Both halves move
together, or "confirm" degrades into "re-investigate."

### A. Capture side — record the anchor

- **`references/concept-template.md`** — add an optional `## Verify` block to the skeletons, modelling the
  *good* form and stating the text-not-link rule:
  ```markdown
  ## Verify
  - <file:symbol> — <what it should show>
  - run: <one-line grep/command> — expected: <result>
  ```
- **`SKILL.md`** — document the convention *and the quality bar* (good vs weak anchor, text-not-link,
  path convention) next to the frontmatter/linking guidance. If a fact is genuinely not code-checkable,
  say so explicitly rather than writing a hollow anchor.
- **`capture.md` / `refine.md`** — **fold into existing steps, not new ones** (capture is already dense):
  capture records the anchor **and a `verified:` stamp** (the commit/time the anchor was confirmed
  against — the freshness gate's baseline) inside its "Compose the concept" step; refine gets a one-line
  nudge that a fact change must update the `## Verify` anchor *and* re-stamp `verified:`, and that a
  verifier-routed refine executes here.

### B. Read side — trust on face, dispatch verification

- **`query.md` (primary).** Answer from the concepts and **trust them on face value** — the answer is not
  blocked on verification. Then, for the concepts the answer *relied on*:
  - **Run the freshness gate** (cheap, sync): is the anchored file changed since the concept's `verified:`
    stamp? Unchanged → done. The answer already stands; nothing spawned.
  - **On a changed anchor → dispatch a background `wiki-verifier`** (Sonnet) and finish the turn. Note in
    the answer that the relied-on claim is being verified in the background (so the user knows a `STALE:`
    correction may follow). **Escalate to inline** only for an act-now-high-stakes claim or a quick `run:`
    anchor.
  - **Anchor missing/unresolvable here** → answer from the wiki with a "couldn't-verify (no anchor / not
    present here)" label; flag the missing anchor as a curation gap. Never refuse, never auto-refine.
  - The existing "answer only from concepts you read" rule gets a one-line carve-out: a verification read
    against the named anchor (inline or by the dispatched verifier) is the sanctioned confirm step, not
    "filling from general knowledge," and is scoped to that anchor — not license to re-investigate.
- **`agents/wiki-verifier.md` (new).** A Sonnet, near-read-only sibling to `wiki-explorer`. Input: a
  concept + its `## Verify` anchor. It checks the anchor against current state and returns
  **confirmed / stale (+why) / couldn't-verify**. On **objective `run:` divergence** it performs the gated
  refine itself (Decision 2 guards) and surfaces one line; on a prose-only "looks stale" it **reports**
  and proposes `/refine`, never rewriting from a cheap model's opinion. Lightweight stop rule: check the
  named spot and only that spot.
- **`SKILL.md` — a "Reading is trust-but-verify" principle**, symmetric to "Reading is permissive": trust
  the summary, use it now, let the freshness gate + background verifier confirm/heal. Inheritance scoped:
  *query* runs the gate + dispatch; *explore* carries the trust-but-verify mindset only (hard read-only,
  no Grep/Bash — navigation framing, not verification).
- **Hooks** (`hook_session_start.py`, `hook_user_prompt.py`) — **replace words, don't append**: fold
  "consult, then confirm against current state before relying — the wiki says where to look, so it's
  quick" into the existing consult sentence so net length stays flat (the once-per-session nudge is
  already dense; appending makes it a wall of text the model skims past). The "so it's quick" clause is
  load-bearing — it stops the reframe reading as "more work." No per-turn pressure is added.

## Scope — MVP now, fast-follow later

The review (simplicity + adoption lenses) converged: build the smallest end-to-end slice, prove anchors
pay off, *then* wire the maintenance/bulk sides.

**MVP (ship together — the irreducible capture⇄read loop + dogfood credibility):**
- `SKILL.md` — the "trust-but-verify" principle + the `## Verify` convention & quality bar.
- `references/concept-template.md` — the `## Verify` skeleton + the `verified:` stamp.
- `capture.md` — record the anchor + `verified:` stamp (folded into Compose).
- `query.md` — trust-on-face + the **freshness gate** + dispatch (inline-escalate or background).
- `agents/wiki-verifier.md` (new) — the Sonnet background verifier (confirm / stale+why / couldn't-verify;
  objective-divergence self-heal).
- `refine.md` — one-line "update the anchor + re-stamp `verified:`; a verifier-routed refine executes here."
- the two nudge hooks — word-swap reframe.
- **Backfill `## Verify` + `verified:` on the 8 existing concepts.** This repo is the canonical living
  example (per CLAUDE.md); shipping the ethos while the example bundle violates it undercuts it. Cheap now
  (each was written from code the author knows), costly later — and it's the first real test of the loop.

> **Optional staging** if you want value sooner: land the gate + trust-on-face + an *inline* "anchor
> changed → may be stale" note first (no subagent), then add `wiki-verifier` as the second step. The
> background subagent is the payoff but also the most moving parts; the gate alone already removes the
> per-read tax.

**Deferred fast-follow (once anchors exist and the loop has been exercised):**
- `ingest.md` + `agents/wiki-explorer.md` anchor wiring (bulk bootstrap — re-runnable, backfillable;
  don't mass-produce anchors in a shape the read loop might prove wrong).
- The two `/tend` checks (missing/weak anchor; dangling-path). These are the plan's *only* real
  script+fixture cost and are **redundant with lazy query-confirm** (which catches a bad anchor exactly
  when a claim depends on it). When added, the high-value one flags **weak/prose-only** anchors, not just
  absent ones; the path-resolution check is lower-value (false positives on moves; overlaps R4) — add it
  only if real `/tend` output earns it.

## Nuances / guardrails (unchanged, reinforced)

- **Lightweight is the whole point** — and it is the thing most likely to drift; that's why the stop rule
  is baked into the query step text, not left to the design doc.
- **Flag ≠ author.** A lightweight glance can flag doubt; authoring a correct rewrite needs re-derivation,
  which belongs on the refine surface — never inline in the read path.
- **No new Doctor rule** — the anchor is a convention; the Doctor stays codebase-agnostic.

## Test/verification note

MVP is entirely model-instruction (markdown) — not covered by the deterministic corpora; verify by a real
`/llm-wiki:query` run on a backfilled concept (confirm a fresh `## Verify` anchor resolves and the
verdict + proportional behavior read well). The only piece that would carry a fixture is the deferred
`/tend` anchor-resolution helper, if implemented as a script rather than command prose.
