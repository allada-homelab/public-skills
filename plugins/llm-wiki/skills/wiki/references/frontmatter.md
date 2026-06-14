# Concept frontmatter (OKF v0.1)

Every concept file opens with a YAML frontmatter block delimited by `---`, then a markdown body.

## Required

- **`type`** *(required, non-empty)* — what kind of concept this is. Any string; the producer chooses
  the vocabulary. Examples: `Reference`, `Runbook`, `Decision`, `Convention`, `Gotcha`, `BigQuery Table`,
  `Metric`, `Service`, `API`. This is the **only** field OKF requires.

## Recommended (optional)

| Field | Type | Notes |
|---|---|---|
| `title` | string | Human-readable name. |
| `description` | string | One-line summary; surfaced in `index.md` bullets. |
| `resource` | string (URL/URI) | Link to the thing the concept describes (console, repo, dashboard). |
| `tags` | list of strings | Free-form labels. Written as a simple block list (see below). |
| `timestamp` | string (ISO-8601) | When the concept was last meaningfully updated, e.g. `2026-06-14T14:30:00Z`. |

Custom keys are allowed; unknown keys are preserved by consumers, never stripped.

## Shape the Doctor's restricted parser accepts

Keep frontmatter to scalars and simple block lists — that is what `scripts/doctor.py` parses:

```yaml
---
type: "BigQuery Table"
title: Orders
description: One row per completed customer order.
resource: https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders
tags:
  - sales
  - revenue
timestamp: 2026-05-28T14:30:00Z
---
```

Avoid (these trip the parser → reported as R1):

- nested maps (`a:` then indented `b: c`)
- flow collections (`tags: [sales, revenue]`, `{ ... }`)
- tab indentation
- an unterminated quote or a block that never closes with `---`

Quoting is optional for scalars; quote when the value contains a colon or leading special character
(e.g. `type: "BigQuery Table"`).
