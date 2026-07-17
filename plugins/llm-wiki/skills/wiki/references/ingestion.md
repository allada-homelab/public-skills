# Repository ingestion — bounded coprocessor playbook

`/llm-wiki:ingest` is one causal, parallel-read/single-write pipeline. Deterministic code owns source
scope, topology, dedupe backstops, provenance, and publication; Sonnet Explorers only propose grounded
concepts from exact manifests.

## Scope budgets

| Scope | Explorers | Total concept cap | Intent |
|---|---:|---:|---|
| `min` | 1 | 4 | Architecture and primary runbook |
| `medium` | up to 2 | 15 | Major subsystems, contracts, runbooks, gotchas |
| `high` | up to 3 | 40 | Broad but curated monorepo bootstrap |

`ingest_plan.py` partitions safe files into disjoint manifests. It excludes the wiki, symlinks,
credentials, `.git`, dependency/vendor trees, and generated build output. A truncated manifest is named;
workers never search around it. Each Explorer is dispatched as
`subagent_type: llm-wiki:wiki-explorer` and receives one controller child job, scope/hash,
manifest, and concept budget and returns a raw `evidence_packet` with `purpose: ingest_proposal`.

## Synthesis

- Reject source paths outside the worker's exact manifest and mismatched job/run/scope/hash fields.
- Name failed workers and continue as a partial result; never silently omit one.
- Dedupe slug/title/topic across workers and the recursive catalog before any write.
- Prefer fewer dense concepts; preserve objective claim classifications and source paths.
- `--into <section>` is authoritative. Otherwise, an existing section is selected only when its entire
  token sequence is the unique longest match in a concept's evidence paths. Ties/no match stay at root.
  This routes into known topology without inventing taxonomy.
- The champion chooses any repository-specific section map. llm-wiki supplies the mechanism and never
  infers team ownership or service boundaries as fact.

## One publication boundary

Compose a single ingest-batch JSON from accepted proposals. `batch_publication.py` rechecks HEAD and
source existence, enforces manifest membership, computes hashes, applies topology/dedupe, and stamps
stable claim/evidence provenance. `bundle_ops.py batch-apply` then holds one lock across one mirror,
secret scan, strict Doctor gate, index rebuild, single log entry, and live copy. Workers never write and
individual proposals never publish independently. Staleness or any gate failure leaves the concept
batch unapplied; crash-atomic filesystem commit remains deferred hardening.

`--dry-run` stops before both publication commands and prints paths, sections, duplicates, truncation,
and failed worker names. A successful non-dry run is one git-reversible diff.
