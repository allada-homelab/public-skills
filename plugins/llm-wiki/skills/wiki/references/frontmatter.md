# Concept frontmatter (OKF v0.2)

Every concept file opens with a YAML frontmatter block delimited by `---`, then a markdown body.

## Required

- **`type`** *(required, non-empty)* — what kind of concept this is. Any string; the producer chooses
  the vocabulary. Examples: `Reference`, `Runbook`, `Decision`, `Convention`, `Gotcha`, `BigQuery Table`,
  `Metric`, `Architecture`, `API`. This is the **only** field OKF requires.

## Recommended (optional)

| Field | Type | Notes |
|---|---|---|
| `title` | string | Human-readable name. |
| `description` | string | One-line summary; surfaced in `index.md` bullets. |
| `resource` | string (URL/URI) | Link to the thing the concept describes (console, repo, dashboard). Use an **external URI**, not a relative path to another concept: only **body** markdown links are rewritten by `/llm-wiki:reorganize` and checked by the Doctor's R4 — a `resource:` pointing at a sibling concept would silently break on a move. Inter-concept links belong in the body. |
| `tags` | list of strings | Free-form labels. Written as a block list or a flow list (see below). |
| `status` | `draft` / `stable` / `deprecated` | Optional lifecycle marker. Absent means `stable` — don't write `status: stable` explicitly, only `draft` or `deprecated`. |
| `stale_after` | date (`YYYY-MM-DD`) | Optional. The concept is stale once today >= this date. |

## Provenance and trust (optional families)

- **`generated: { by, at }`** — how the current content was produced. **Code-stamped, not
  author-written**: `bundle_ops apply` stamps it if absent, and the publication path stamps it with the
  model that actually ran. Never hand-write `generated` in a draft — leave it out and let the write path
  fill it in.
- **`verified`** — who/what has confirmed the concept's `## Verify` anchor against current state, and
  when. This one **is** author/agent-written. A single confirmation is a mapping:
  `verified: { by: human:davidallada, at: 2026-07-29T14:30:00Z }`. Multiple independent confirmations are
  a block list of such mappings — consumers treat a bare mapping as a one-element list. Meaning is
  unchanged from before: the read-side freshness gate compares the anchored file's last change to the
  latest `at`; stale → re-verify. Re-stamp on every capture that re-confirms the fact.
- **`sources`** — a list of provenance entries this concept derives from. Within an entry, `resource` is
  required (an absolute URL, a bundle-relative path, a relative path, or a scope descriptor like
  `all queries in project X`); `id`, `title`, `author`, `usage_count`, and `last_modified` are optional.
  Give an entry an `id` when the body cites it via a footnote — `sharded daily.[^ga4-schema]` /
  `[^ga4-schema]: GA4 export schema` — the footnote label is the join key into `sources[].id`, and a
  footnote whose label matches no `id` gets a Doctor warning. A sibling `usage_window: { from, to }`
  frames every `usage_count`.

### Actor convention

Every identity field (`generated.by`, `verified[].by`, `sources[].author`) uses one of three forms:

- `<producer>/<version>` for this plugin's own writes — `llm-wiki/<model>`, e.g. `llm-wiki/claude-opus-5`.
- `human:<id>` for a person, e.g. `human:davidallada`.
- `process:<id>` for an automated process, e.g. `process:llm-wiki-verifier`.

The Doctor errors on an identity string that matches none of these three forms.

Custom keys are allowed; unknown keys are preserved by consumers, never stripped.

## Shape the Doctor's parser accepts

`scripts/doctor.py` now parses scalars, block lists, flow collections (`{ by: x, at: y }`,
`tags: [a, b]`), nested block mappings, and block lists of mappings:

```yaml
---
type: "BigQuery Table"
title: Orders
description: One row per completed customer order.
resource: https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders
tags: [sales, revenue]
verified:
  by: human:davidallada
  at: 2026-07-29T14:30:00Z
sources:
  - id: bq-console
    resource: https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders
    title: BigQuery console for this table
---
```

Still rejected (reported as R1):

- tab indentation
- an unterminated quote, or a flow/block structure that never closes

Quoting is optional for scalars; quote when the value contains a colon or leading special character
(e.g. `type: "BigQuery Table"`).
