# Concept template (copy-paste, conformant)

Start from this skeleton when authoring a new concept. It is aligned to the Doctor's `good` fixture, so
filling it in (and keeping the frontmatter shape) passes strict-producer mode on the first try.

```markdown
---
type: <concept type — prefer a canonical lowercase token: reference | runbook | decision | gotcha | convention | howto | schema | metric | note>
title: <Human-readable name>
description: <One-line summary surfaced in index.md.>
tags:
  - <tag>
timestamp: <YYYY-MM-DDThh:mm:ssZ>
verified: <YYYY-MM-DDThh:mm:ssZ>
---
# <Title>

<Body. Explain the concept. Use sections as needed.>

## Verify
- <file:symbol> — <what current state should show to confirm this>
- run: <one-line grep/command> — expected: <result>

## Related
- See [<Other concept>](./<other-concept>.md) — <how it relates>.
```

Rules to keep while editing:

- `type` must stay present and non-empty (R2). Prefer a canonical lowercase token — `concept`,
  `decision`, `gotcha`, `convention`, `runbook`, `architecture`, `howto`, `reference`, `schema`,
  `metric`, `api`, `dataset`, `table`, `evaluation`, `note`; the Doctor's R5 warns (report-only, never
  blocks) on anything else. Everything else is optional.
- Keep frontmatter to scalars and simple `- item` lists — no nested maps or flow `[...]` (R1).
- Use relative `./name.md` links (see `linking.md`).
- Omit any optional field you don't have rather than leaving an empty placeholder.
- **`## Verify` is the confirmation anchor** — free-form text, **not** a markdown link (a real link
  into repo code trips the Doctor's R4 link-health with false broken-link warnings). A good anchor is
  *checkable*: a resolvable `file:symbol` (e.g. `scripts/doctor.py:parse_frontmatter`) or a runnable
  `run: <one-liner> — expected: <result>`. **Never** prose-only ("see the code"); **never** a bare
  `file:line` (line numbers rot on the first edit above them → false verdicts). Use **repo-root-relative
  paths**, resolved against `${CLAUDE_PROJECT_DIR}`. Pair with a **`verified:`** frontmatter stamp
  (ISO-8601) — when the anchor was last confirmed against current state. Omit both for a concept that is
  genuinely not code-verifiable (say "not code-verifiable; confirm via …" instead).

Failure→fix (gotcha) shape — use this when the finding is a **wrong approach you tried and the right one
that worked**, so the next session doesn't repeat the mistake:

```markdown
---
type: gotcha
title: <Short name for the trap>
description: <The wrong approach and the right one, in one line.>
tags:
  - gotcha
timestamp: <YYYY-MM-DDThh:mm:ssZ>
verified: <YYYY-MM-DDThh:mm:ssZ>
---
# <Title>

**Symptom / context.** <When this comes up.>

**What does not work.** <The approach that was tried, and how it fails.>

**What works.** <The correct approach.>

**Why.** <The underlying reason — so the fix generalizes instead of being cargo-culted.>

## Verify
- <file:symbol or run: one-liner> — <what confirms the fix is still correct>
```

Minimal valid concept (the floor):

```markdown
---
type: reference
---
# Whatever
Body.
```
