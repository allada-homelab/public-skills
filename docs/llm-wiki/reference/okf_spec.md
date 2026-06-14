# Open Knowledge Format (OKF) v0.1 — Spec Reference

> Reference notes compiled 2026-06-14 from `GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md`,
> the `okf/` directory, and the `toolbox/mdcode/demo` reference implementation. Captures the
> actual spec rules (not the blog paraphrase). See `okf_repo.md` for source links.

## 1. Core Terminology

| Term | Definition |
|---|---|
| **Knowledge Bundle** | Self-contained hierarchical directory of markdown files; the unit of distribution |
| **Concept** | A single `.md` file representing one unit of knowledge |
| **Concept ID** | The file path minus the `.md` suffix (e.g. `tables/users`) |
| **Frontmatter** | YAML metadata block delimited by `---` at the top of a file |
| **Body** | All markdown content after the frontmatter block |

## 2. Bundle Structure

```
path/to/bundle/
├── index.md              # Reserved — optional directory listing
├── log.md                # Reserved — optional update history
├── <concept>.md          # Root-level concept document
└── <subdirectory>/
    ├── index.md          # Reserved in each subdirectory
    ├── <concept>.md
    └── <subdirectory>/
```

**Reserved filenames:** `index.md` and `log.md`. These have defined meanings and **cannot be used as concept documents**.

**Distribution options** (per spec): git repository (recommended), tarball, zip archive, or subdirectory within a larger repo.

## 3. Frontmatter Fields

### Required (hard rule — governs conformance)

| Field | Type | Constraint |
|---|---|---|
| `type` | string | Must be non-empty. Identifies the concept kind (e.g., `"BigQuery Table"`, `"Metric"`, `"Playbook"`). **Only required field.** |

### Recommended (conventional — not enforced)

| Field | Type | Notes |
|---|---|---|
| `title` | string | Human-readable display name |
| `description` | string | Single-sentence summary |
| `resource` | URI string | Uniquely identifies the underlying asset |
| `tags` | YAML list | Cross-cutting categorization |
| `timestamp` | ISO 8601 datetime | Last-modified time (e.g. `2026-05-28T14:30:00Z`) |

- **Producer rule:** May add arbitrary custom keys beyond the above.
- **Consumer rule:** Must preserve unknown fields; must tolerate unrecognized `type` values.

## 4. Concept Identity and File Paths

A concept's identity (Concept ID) is its file path relative to the bundle root, with the `.md` suffix stripped.

- `tables/orders.md` → Concept ID: `tables/orders`
- `datasets/sales.md` → Concept ID: `datasets/sales`

There is no separate ID field in frontmatter; the path **is** the identity.

## 5. Cross-Linking Rules

### Absolute (bundle-relative) links — **recommended form**
Begin with `/`, resolved from the bundle root:
```markdown
See [customers table](/tables/customers.md) for the join key.
```
Stable when documents move within the bundle.

### Relative links — standard markdown
```markdown
See [neighboring concept](./other.md).
```

### Semantics
- Links assert relationships; the **specific relationship type is conveyed by surrounding prose**, not the link syntax itself.
- Consumers typically treat all links as **undirected edges**.
- **Broken links are tolerated** — they may represent not-yet-documented knowledge. Consumers must not reject a bundle for broken links.

## 6. Reserved File Structures

### `index.md`
- No frontmatter (exception: root `index.md` may contain `okf_version: "0.1"` in frontmatter — the **only** location where frontmatter is permitted in an index file).
- Lists concepts under section headings:
```markdown
# Section Heading

* [Title 1](relative-url-1) - short description
* [Title 2](relative-url-2) - short description
```
- Entries should include descriptions pulled from linked concepts' frontmatter.
- May be auto-generated or synthesized at consumption time.

### `log.md`
- Records change history, newest entries first.
- Date headings use ISO 8601 `YYYY-MM-DD` format.
- Bold prefix conventions: `**Update**`, `**Creation**`, `**Initialization**`.
```markdown
# Directory Update Log

## 2026-05-22
* **Update**: Added [Customer Metrics](/tables/customer-metrics.md).
```

## 7. Body Conventions

Standard markdown body. Conventional (not required) section headings:

| Heading | Purpose |
|---|---|
| `# Schema` | Structured description of the asset (tables, fields, etc.) |
| `# Examples` | Usage examples with fenced code blocks |
| `# Citations` | Numbered external source references |

Citations format:
```markdown
# Citations

[1] [BigQuery announcement](https://cloud.google.com/blog/...)
[2] [Internal runbook](https://wiki.acme.internal/data/quality)
```
Citations may be absolute URLs, bundle-relative paths, or references to subdirectory concepts.

## 8. Conformance Criteria (Section 9 of spec)

A bundle **conforms to OKF v0.1** if and only if:

1. Every non-reserved `.md` file contains **parseable YAML frontmatter**.
2. Every frontmatter block contains a **non-empty `type` field**.
3. Reserved filenames (`index.md`, `log.md`) follow their specified structures.

**Consumers MUST NOT reject bundles for:**
- Missing optional fields (`title`, `description`, `resource`, `tags`, `timestamp`)
- Unknown `type` values
- Unknown frontmatter keys
- Broken cross-links
- Missing `index.md` files

The spec explicitly calls this a "permissive model" to allow bundles to be partially agent-generated and to evolve over time.

## 9. Versioning

- Scheme: `<major>.<minor>`
- **Minor bump:** backward-compatible additions
- **Major bump:** breaking changes
- Bundles declare version via `okf_version: "0.1"` in root `index.md` frontmatter only.
- Consumers should attempt best-effort consumption of unknown versions rather than rejecting them.

## 10. Reference Implementations

### Enrichment Agent (producer — `okf/src/enrichment_agent/`)
Two-pass LLM pipeline:
1. **BigQuery pass:** Writes one OKF document per concept from BigQuery metadata.
2. **Web pass:** LLM with web-crawling enriches existing concepts or creates new reference documents from seed URLs. Constrained by `--web-max-pages` and domain filters.

CLI:
```bash
python -m enrichment_agent enrich \
    --source bq --dataset <project>.<dataset> \
    --web-seed-file seeds.txt --out ./bundles/<name>
```

### Static HTML Visualizer / `mdcode` demo (consumer)
```bash
python -m enrichment_agent visualize --bundle ./bundles/<name>
```
Produces an interactive `viz.html` file. The `toolbox/mdcode/demo/okf/` TypeScript demo (`setup.ts`, `cleanup.ts`) maps each `.md` file path to a Dataplex catalog entry, storing the markdown body on the `dataplex-types.global.overview` aspect.

### Sample bundle on disk (`okf/bundles/ga4/` — 17 files)
```
ga4/
├── index.md          # Lists datasets/, references/, tables/
├── viz.html          # Generated visualizer
├── datasets/
│   ├── index.md
│   └── <dataset>.md
├── references/
│   ├── index.md
│   └── metrics/
│       └── event_count.md   # Concept ID: references/metrics/event_count
└── tables/
    ├── index.md
    └── <table>.md
```

## 11. Items the Spec Leaves Unspecified

- No validation tooling is mandated (schema validators, linters).
- No prescribed way to declare the `resource` URI scheme — any URI is accepted.
- Relationship typing between linked concepts (type is prose-only, no formal predicate vocabulary).
- No required `okf_version` in bundles — the version declaration in `index.md` frontmatter is optional.
- No mechanism for concept deletion or deprecation (only `log.md` conventions).
- The `references/` subdirectory naming is a convention visible in example bundles, not a reserved name in the spec.
