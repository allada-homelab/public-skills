# Concept template (copy-paste, conformant)

Start from this skeleton when authoring a new concept. It is aligned to the Doctor's `good` fixture, so
filling it in (and keeping the frontmatter shape) passes strict-producer mode on the first try.

```markdown
---
type: "<concept type, e.g. Reference | Runbook | Decision | BigQuery Table>"
title: <Human-readable name>
description: <One-line summary surfaced in index.md.>
tags:
  - <tag>
timestamp: <YYYY-MM-DDThh:mm:ssZ>
---
# <Title>

<Body. Explain the concept. Use sections as needed.>

## Related
- See [<Other concept>](./<other-concept>.md) — <how it relates>.
```

Rules to keep while editing:

- `type` must stay present and non-empty (R2). Everything else is optional.
- Keep frontmatter to scalars and simple `- item` lists — no nested maps or flow `[...]` (R1).
- Use relative `./name.md` links (see `linking.md`).
- Omit any optional field you don't have rather than leaving an empty placeholder.

Failure→fix (gotcha) shape — use this when the finding is a **wrong approach you tried and the right one
that worked**, so the next session doesn't repeat the mistake:

```markdown
---
type: Gotcha
title: <Short name for the trap>
description: <The wrong approach and the right one, in one line.>
tags:
  - gotcha
timestamp: <YYYY-MM-DDThh:mm:ssZ>
---
# <Title>

**Symptom / context.** <When this comes up.>

**What does not work.** <The approach that was tried, and how it fails.>

**What works.** <The correct approach.>

**Why.** <The underlying reason — so the fix generalizes instead of being cargo-culted.>
```

Minimal valid concept (the floor):

```markdown
---
type: Reference
---
# Whatever
Body.
```
