# Open Knowledge Format (OKF) v0.2 — Spec Reference

> Reference notes compiled 2026-07-29 from `GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md`
> at OKF **v0.2**, superseding the earlier v0.1 notes below. Captures the actual spec rules
> (not the blog paraphrase). Section numbers (`§n`) refer to the upstream spec so the Doctor
> implementation can be traced back to them. See `okf_repo.md` for source links.

## 1. Core Terminology (§2)

| Term | Definition |
|---|---|
| **Knowledge Bundle** | Self-contained hierarchical directory of markdown files; the unit of distribution |
| **Concept** | A single `.md` file representing one unit of knowledge |
| **Concept ID** | The file path minus the `.md` suffix (e.g. `tables/users`) |
| **Frontmatter** | YAML metadata block delimited by `---` at the top of a file |
| **Body** | All markdown content after the frontmatter block |
| **Link** | A standard markdown link expressing a relationship between concepts |
| **Source** | A material a concept derives from, recorded in `sources` (§5.1) |
| **Provenance** | The set of sources a concept derives from |
| **Credibility signal** | An objective per-source fact (`author`, `usage_count`, `last_modified`) used to *infer* trust — not a stored score (§5.1) |
| **Actor** | An identity string: `<producer>/<version>`, `human:<id>`, or `process:<id>` (§7) |
| **Trust tier** | A level derived from `verified`: unverified, machine-confirmed, human-reviewed (§5.3) |
| **Attested Computation** | A concept (`type: Attested Computation`) carrying a sanctioned, checkable computation (§10) |

## 2. Bundle Structure (§3)

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

**Reserved filenames (§3.1):** `index.md` and `log.md`. These have defined meanings and
**MUST NOT be used as concept documents**, at any level of the hierarchy.

**Distribution options** (§3): git repository (recommended — history, attribution, diffs),
tarball, zip archive, or subdirectory within a larger repo.

A `tags` frontmatter field (§4.1) is the first-class way to classify concepts. OKF does not
specify a separate file format for tag aggregation; a consumer wanting a tag-browsing view
synthesizes one at consumption time from frontmatter.

## 3. Frontmatter Fields (§4.1)

### Required (hard rule — governs conformance)

| Field | Type | Constraint |
|---|---|---|
| `type` | string | Must be non-empty. Identifies the concept kind (e.g., `"BigQuery Table"`, `"Metric"`, `"Playbook"`, `"Attested Computation"`). **The only always-required field** — a concept carrying just `type` is fully conformant (§11). |

### Recommended (conventional — not enforced)

| Field | Type | Notes |
|---|---|---|
| `title` | string | Human-readable display name. Absent ⇒ consumers MAY derive one from the filename. |
| `description` | string | Single-sentence summary, used by index generators and search snippets. |
| `resource` | URI string | Canonical URI for the underlying asset. Absent for concepts describing abstract ideas. |
| `tags` | YAML list | Cross-cutting categorization. |

The optional **provenance/trust/lifecycle** families (§5) and the **computation** fields for
`Attested Computation` concepts (§10) may also appear — see sections below.

- **Producer rule:** MAY add arbitrary custom keys beyond the above.
- **Consumer rule:** SHOULD preserve unknown fields when round-tripping; MUST NOT reject a
  document for unrecognized fields or an unrecognized `type` value.

> **v0.1 note:** the recommended `timestamp` field is superseded by `generated.at` (§13.1) —
> see §7 below. It is no longer part of the current field set.

## 4. Concept Identity and File Paths (§2)

A concept's identity (Concept ID) is its file path relative to the bundle root, with the
`.md` suffix stripped.

- `tables/orders.md` → Concept ID: `tables/orders`
- `datasets/sales.md` → Concept ID: `datasets/sales`

There is no separate ID field in frontmatter; the path **is** the identity.

## 5. Cross-Linking and Paths (§6)

### Links between concepts (§6.1)

**Absolute (bundle-relative) links — recommended form.** Begin with `/`, resolved from the
bundle root:
```markdown
See [customers table](/tables/customers.md) for the join key.
```
Stable when documents move within their subdirectory.

**Relative links** — standard markdown:
```markdown
See [neighboring concept](./other.md).
```

**Semantics:** a link asserts a relationship; the specific kind (parent/child, references,
joins-with, depends-on) is conveyed by the **surrounding prose**, not the link syntax itself.
Consumers that build a graph view typically treat links as directed edges of an untyped
relationship.

**Broken links MUST be tolerated** (§6.1) — a link whose target does not exist may represent
not-yet-written knowledge. Consumers MUST NOT reject a bundle for broken links.

> Corrected from the v0.1 notes: this tolerance rule lives in **§6.1** in v0.2, not §5.

### Path-valued fields (§6.2)

The following fields name a path or URI: `resource`, `sources[].resource`, `computation`,
`executor.resource`, `attester.resource`. (A `sources[].resource` may instead be a scope
descriptor, §5.1 below, in which case it is not a path.) Each accepts an absolute URL, a
bundle-relative path beginning with `/`, or an ordinary relative path.

### The `references/` convention (§6.3)

A `references/` subdirectory conventionally mirrors external material, run instructions, or
code as first-class concepts within the bundle (e.g. `references/attesters/revenue.py`). It
is a naming convention visible in example bundles, not a name reserved by the spec.

## 6. Reserved File Structures

### `index.md` (§8)
- No frontmatter, with one exception: the **bundle-root** `index.md` MAY carry an
  `okf_version` key (§12) — the **only** location where frontmatter is permitted in an
  index file.
- Lists concepts under section headings, for progressive disclosure:
```markdown
# Section Heading

* [Title 1](relative-url-1) - short description
* [Title 2](relative-url-2) - short description
```
- Entries SHOULD include descriptions pulled from linked concepts' frontmatter.
- Producers MAY generate `index.md` automatically; consumers MAY synthesize one at
  consumption time when none is present.

### `log.md` (§9)
- MAY appear at any level of the hierarchy; records that scope's change history, newest
  entries first.
- Date headings **MUST** use ISO 8601 `YYYY-MM-DD` form.
- Entries are prose; the leading bold word (`**Update**`, `**Creation**`, `**Initialization**`,
  `**Deprecation**`) is a convention, not a requirement.
```markdown
# Directory Update Log

## 2026-05-22
* **Update**: Added [Customer Metrics](/tables/customer-metrics.md).
* **Deprecation**: Retired [Legacy Funnel](/metrics/legacy-funnel.md).
```

## 7. Body Conventions (§4.2)

Standard markdown body. Producers SHOULD favor structural markdown (headings, lists, tables,
fenced code) over freeform prose. No body section is required. These headings are
**conventional** and SHOULD be used when applicable:

| Heading | Purpose |
|---|---|
| `# Schema` | Structured description of an asset's columns/fields. |
| `# Examples` | Concrete usage examples, often as fenced code blocks. |
| `# Computation` | The sanctioned computation of an `Attested Computation` concept (§10). |

**Per-claim attribution** now uses a markdown footnote whose label is a `sources[].id`
(§5.1), not a body `# Citations` list:
```markdown
The `events_` table is sharded daily as `events_YYYYMMDD`.[^ga4-schema]

[^ga4-schema]: GA4 BigQuery Export schema
```

> **v0.1 note:** the body `# Citations` heading is superseded by frontmatter `sources`
> (§13.1). Consumers MAY still parse a legacy `# Citations` list on v0.1 documents.

## 8. Provenance, Trust, and Lifecycle (§5)

These frontmatter families make "where did this come from," "how much should I trust it,"
and "is it still current" answerable from frontmatter alone. **All are optional** — their
absence is meaningful (an unverified concept is distinguishable from a verified one) but
never a rejection reason (§11).

### 8.1 Provenance: `sources` (§5.1)

```yaml
sources:
  - id: ga4-schema
    resource: https://developers.google.com/analytics/bigquery/export-schema
    title: GA4 BigQuery Export schema
    author: team:ga4-docs
    usage_count: 5000
    last_modified: 2026-05-30
usage_window: { from: 2026-06-01, to: 2026-06-30 }
```

Per-entry fields:

| Field | Required? | Shape / notes |
|---|---|---|
| `resource` | **REQUIRED** within an entry | An absolute URL, bundle-relative path, or `references/` path the consumer *can* follow; OR a scope descriptor it cannot (e.g. `all queries in BigQuery project X`). |
| `id` | Optional | Stable key for per-claim attribution (below). SHOULD be present when the body cites the source. |
| `title` | Optional | Human-readable label. |
| `author` | Optional (credibility signal) | Who/what produced the source, in the actor convention (§7). An authority signal. |
| `usage_count` | Optional (credibility signal) | How often `resource` was exercised over `usage_window`. An adoption/liveness signal. |
| `last_modified` | Optional (credibility signal) | `YYYY-MM-DD` the source itself last changed — distinct from `generated.at` (§5.2), which is when the *concept* was written. |

`usage_window` is written once as a sibling of `sources` and frames every `usage_count` with
a `{ from, to }` range; a single entry MAY override it with its own `usage_window`.

**Why credibility is inferred, not scored:** OKF records the objective per-source signals
above so a consumer can judge trust from the sources a concept was extracted from. It does
not store a credibility score — a score is subjective, unportable across consumers, and goes
stale. `usage_count` in particular is coarse: comparable at the alive-vs-dead and
order-of-magnitude level, and against a source's own history, but not as a precise
cross-kind ranking (a scheduled query's executions and a human's deliberate dashboard views
don't carry equal weight).

Lineage is expressed through links (§6), not a dedicated field: when a `resource` points at
another OKF concept, the derivation edge already exists in the bundle graph, and a consumer
MAY recurse into that source's own `sources`. Deeper lineage (an explicit external
`derived_from`, or data lineage) is out of scope for v0.2.

**Per-claim attribution:** a markdown footnote whose **label is a `sources[].id`**:
```markdown
The `events_` table is sharded daily as `events_YYYYMMDD`.[^ga4-schema]

[^ga4-schema]: GA4 BigQuery Export schema
```
The footnote label is the join key into `sources`; consumers resolve attribution through the
matching entry, not by parsing footnote prose. The join is **keyed, not positional**
(`sources[0]`) because agents constantly rewrite these documents — a positional index
misattributes silently the moment the list is reordered, whereas a stable `id` survives
reordering.

### 8.2 Trust: `generated` and `verified` (§5.2)

Kept distinct because who *wrote* a concept need not be who *confirmed* it.

```yaml
generated: { by: reference_agent/gemini-2.5-pro, at: 2026-06-20T22:53:05Z }
```

| Field | Required? | Meaning |
|---|---|---|
| `generated.by` | **REQUIRED** within `generated` | An actor (§7) — who/what produced the content. |
| `generated.at` | Optional | ISO 8601 datetime of the content's **last meaningful change**. Lets consumers tell a recent edit from a stale fact. |

```yaml
verified:
  - { by: human:ahormati, at: 2026-06-25T09:00:00Z }
  - { by: process:finance-nightly, at: 2026-06-26T02:00:00Z }
```

- `verified` is a **list** of `{ by, at }` verification events (multiple entries capture
  independent checks — a human sign-off plus a nightly process). "How recently" is the
  latest `at`.
- `verified` is **independent of `generated.at`**: content can change without
  re-confirmation, and facts can be re-confirmed without regeneration.
- A single verifier MAY be written as a bare mapping without the list dash:
  ```yaml
  verified: { by: human:ahormati, at: 2026-06-25T09:00:00Z }
  ```
  Consumers **MUST** treat a bare `verified` mapping as a one-element list.

### 8.3 Trust tiers (§5.3)

Derived from `verified`, lowest to highest:

| Tier | Condition |
|---|---|
| **unverified** | No `verified` key. |
| **machine-confirmed** | `verified` present, by non-`human:` actors only. |
| **human-reviewed** | `verified` includes at least one `human:<id>` actor. |

A concept with no trust frontmatter is still consumable — consumers MUST NOT reject it
(§11). Trust tiers are advisory signals, not access control.

### 8.4 Lifecycle: `status` (§5.4)

```yaml
status: stable        # draft | stable | deprecated
```

| Value | Meaning |
|---|---|
| `draft` | Not yet reviewed; possibly incomplete. |
| `stable` | Default; ready for consumption. |
| `deprecated` | Kept for links and history; no longer current. |

**Absent `status` ⇒ `stable`.**

### 8.5 Lifecycle: `stale_after` (§5.5)

```yaml
stale_after: 2026-09-23   # absolute date
```

Optional. An **absolute date** (`YYYY-MM-DD`); a concept is stale when `today >= stale_after`.
Deliberately absolute rather than a relative TTL, so the staleness decision is a plain date
comparison with no reference to when the concept was read.

## 9. Actor Convention (§7)

Fields that record an identity (`generated.by`, `verified[].by`) use one convention:

| Form | Meaning | Example |
|---|---|---|
| `<producer>/<version>` | An agent or tool | `reference_agent/gemini-2.5-pro` |
| `human:<id>` | A person | `human:ahormati` |
| `process:<id>` | An automated process | `process:finance-nightly` |

**Trust classification (§5.3) keys off the `human:` prefix** — producers MUST use it for
hand-authored or human-confirmed content, or that content will not be recognized as
human-reviewed.

## 10. Attested Computations (§10) — reference only, not adopted by this plugin

> **This repo's Doctor does not implement or validate this section.** `llm-wiki` never
> authors an `Attested Computation` concept, and none of the fields below (`runtime`,
> `parameters`, `computation`, `executor`, `attester`) are checked by `doctor.py`. Summarized
> here for completeness only, in case a future phase adopts it.

An `Attested Computation` concept (`type: Attested Computation`) carries a sanctioned way to
*compute* a value, distinct from provenance (which answers "where did this claim come
from"). It is its own concept — other concepts link to it — because `runtime` defines what
`parameters` mean, one computation can back many consumers, and trust state (`verified`,
`stale_after`, `attester`) is per computation.

Contract fields (§10.2): `runtime` (**REQUIRED** for this type — e.g. `bigquery`, `dbt`,
`python`), `parameters` (typed named holes: `{ name, type, required }`), `computation`
(optional path to the computation file; absent ⇒ the body `# Computation` fence is used),
`executor` (`resource` + `receipt` shape — how the computation is run and what evidence a
run returns), and `attester` (deterministic, no-LLM code that inspects a receipt and returns
a verdict). §10.5–10.6 describe the discover/load/parameterize/execute/attest/gate consumer
flow (informative) and note that `verified` (doc-level, confirms the *definition*) and
attestation (per-run, confirms the *execution*) are distinct and both needed.

## 11. Conformance (§11)

A bundle **conforms to OKF v0.2** if and only if these three hard rules hold:

1. Every non-reserved `.md` file contains **parseable YAML frontmatter**.
2. Every frontmatter block contains a **non-empty `type` field**.
3. Every reserved filename (`index.md`, `log.md`) follows its specified structure (§8, §9)
   **when present**.

When the trust/lifecycle/provenance/computation families are present, consumers additionally:
- **MUST** treat a bare `verified` mapping as a one-element list (§5.2).
- **MUST NOT** reject a concept for missing any optional family (§5.3).
- SHOULD derive trust tiers and staleness only from the fields specified in §5, and SHOULD
  surface (not silently drop) a failing attestation (§10.5).

**Consumers MUST NOT reject a bundle for:**
- Missing optional frontmatter fields.
- Unknown `type` values.
- Unknown additional frontmatter keys.
- Broken cross-links.
- Missing `index.md` files.

The spec calls this a "permissive model," allowing bundles to be partially agent-generated
and to evolve over time.

## 12. Versioning (§12)

- Scheme: `<major>.<minor>`.
- **Minor bump:** backward-compatible additions (new optional fields, new conventional
  headings).
- **Major bump:** may make breaking changes (renaming required fields, changing reserved
  filenames).
- Bundles **MAY** declare the version they target with `okf_version: "0.2"` in a
  **bundle-root** `index.md` frontmatter block — the only place frontmatter is permitted in
  an `index.md` (§8). This is optional: upstream's own sample bundles do not actually set
  `okf_version` anywhere. This repo chooses to declare it in its own bundle-root index.
- Consumers that don't understand a declared version SHOULD attempt best-effort consumption
  rather than rejecting the bundle.

## 13. Changes from v0.1 (§13)

v0.2 supersedes v0.1 as a minor bump under §12, except for two deliberate breaking changes.
A v0.1 bundle is consumable by a v0.2 consumer under the fallbacks noted here.

### Breaking (§13.1)

| v0.1 | v0.2 | Consumer fallback |
|---|---|---|
| `timestamp` frontmatter field | `generated.at` (§5.2) | Consumers MAY fall back to a legacy `timestamp` when `generated` is absent. |
| Body `# Citations` list | Frontmatter `sources` (§5.1) | Consumers SHOULD read `sources`; MAY still parse a legacy `# Citations` list on v0.1 documents. |

### Additive (§13.2)

All additive: new optional keys, one new concept type, one new conventional heading. Their
absence yields a plain v0.1 concept.

- New frontmatter families: `sources` with its credibility signals (`author`, `usage_count`,
  `last_modified`) and the `usage_window` sibling; `generated`, `verified`; `status`,
  `stale_after` (§5).
- New concept type `Attested Computation` and its computation keys `runtime`, `parameters`,
  `computation`, `executor`, `attester` (§10).
- New conventional body heading `# Computation` (§4.2).
- The actor convention for `generated.by` and `verified[].by` (§7).

Everything else — bundle structure, reserved filenames, the required `type`, recommended
`title`/`description`/`resource`/`tags`, cross-linking, index files, log files, permissive
conformance — carries forward unchanged.

## 14. Upstream Reference Implementation — and how strict it actually is

Verified against `GoogleCloudPlatform/knowledge-catalog` at v0.2 (the revision landed in one
squashed PR, `780fe9d3`, 2026-07-24). This section exists to calibrate our Doctor: **upstream
enforces far less than we do, deliberately.**

- **Validator.** `okf/src/reference_agent/bundle/document.py` → `OKFDocument.validate()` checks
  exactly one thing: that `type` is present and non-empty (`REQUIRED_FRONTMATTER_KEYS = ("type",)`;
  v0.1 had required four keys). It runs on every write inside `write_concept_doc`, not as a
  standalone CLI. There is **no** reserved-filename check, link-health check, type-vocabulary
  check, family-field validation, or legacy-field warning anywhere upstream.
- **No migration tool exists.** The v0.1 → v0.2 move was done by regenerating and hand-editing
  bundle content, not by a converter. Nothing upstream maps `timestamp` → `generated.at` or parses
  a `# Citations` list into `sources` entries, so our migration logic has no reference to match.
- **No JSON Schema, YAML schema, or formal grammar** ships with the spec; SPEC.md prose plus an
  informal dataclass is the whole contract.
- **CLI.** `python -m reference_agent {enrich,visualize}` — an LLM enrichment producer and a static
  HTML visualizer. No `validate` and no `migrate` subcommand.
- **Sample bundles** (`okf/bundles/`): `ga4`, `stackoverflow`, `crypto_bitcoin` were regenerated in
  v0.2 form and use only `generated` + `sources`; the hand-curated `acme_retail` is the one bundle
  exercising `verified` / `status` / `stale_after`. Real actor strings in them confirm the §7
  convention is producer/**model**: `reference_agent/gemini-3.5-flash`,
  `reference_agent/gemini-2.5-pro`, plus `human:jsmith@acme` and `process:finance-nightly`.
- **None of them declare `okf_version`**, and their root `index.md` files carry no frontmatter at
  all — confirming the declaration is genuinely optional (§12). This repo chooses to declare it
  because the plugin uses it to recognize a bundle root.

The practical consequence: a bundle this plugin's Doctor rejects may still be accepted upstream.
That is intended — we are a *strict producer* of our own bundles, not a gatekeeper of foreign ones,
which is why every rule beyond the three hard conformance rules is either scoped to content we
authored (R6) or report-only (R4, R5, R7, R9).

## 15. Items the Spec Leaves Unspecified

- No validation tooling is mandated (schema validators, linters).
- No prescribed `resource` URI scheme — any URI is accepted.
- Relationship typing between linked concepts (type is prose-only, no formal predicate
  vocabulary).
- No required `okf_version` in bundles — the declaration in root `index.md` frontmatter is
  optional, and upstream's own sample bundles omit it.
- The exact wire format for Attested Computation receipts and verdicts, the attester ABI,
  portability/sandboxing, and attestation caching are explicitly deferred to a future
  revision (§12, "Considered and deferred") — left out of scope here too, beyond the §10
  summary, since this plugin does not adopt §10 at all.
- Semantic-layer (Looker/dbt) attester comparisons where equality shifts from SQL equality
  to model-and-binding equality — also explicitly deferred upstream.
- Whether `usage_count` figures are ever comparable *across* sources of different kinds
  (e.g. a dashboard view vs. a scheduled query run) beyond "don't treat it as a precise
  ranking" — the spec gives the caution but no normalization method, so we leave any
  cross-kind weighting unspecified rather than invent one.
- The `references/` subdirectory naming is a convention visible in example bundles, not a
  reserved name in the spec (§6.3).
