# public-skills

David Allada's public **Claude Code marketplace** — a repository of his own plugins, skills,
and tooling for development use.

## Plugins

### `llm-wiki` — an OKF-native knowledge wiki for Claude Code

Lets Claude build and tend a persistent, portable knowledge base for a project, so each
session starts smarter than the last. The wiki is a directory of markdown "concept" files in
Google's [Open Knowledge Format (OKF) v0.1](./docs/llm-wiki/reference/okf_spec.md) — just files, readable
on GitHub, portable to any OKF consumer. Conformance is **guaranteed by a deterministic Doctor
script**, and every write is **confirm-first** (shown before it lands).

**Commands** (all confirm-first):

| Command | Purpose |
|---|---|
| `/llm-wiki:init` | Bootstrap a conformant bundle (default location `./llm-wiki/`). |
| `/llm-wiki:ingest` | Bootstrap a whole wiki from an existing repo — orchestrated multi-agent ingestion (`--scope min\|medium\|high`, `--dry-run`). |
| `/llm-wiki:capture` | Turn a finding from the current session into one conformant concept. |
| `/llm-wiki:explore` | Navigate the wiki via `index.md` progressive disclosure (read-only). |
| `/llm-wiki:query` | Answer a question grounded in the wiki, with citations and a gap flag. |
| `/llm-wiki:conform` | Run the Doctor and report conformance (read-only). |
| `/llm-wiki:refine` | Edit an existing concept in place; indexes and the log stay correct. |
| `/llm-wiki:prune` | Remove a concept; dangling inbound links are reported, not rewritten. |
| `/llm-wiki:reorganize` | Move/rename concepts (incl. into subdirectories) with zero broken links. |
| `/llm-wiki:tend` | Read-only curation digest (conformance, broken links, staleness, gaps) proposing maintenance. |

Plus the `llm-wiki:wiki` skill (OKF authoring/reading knowledge), and **Phase 3 autonomy** — hooks that
preload the wiki at session start, block credential/non-conformant writes (PreToolUse guards), and nudge
during-work capture; mode in `.claude/llm-wiki.local.md` defaults to `proactive` (auto). Status: **Phases 1 & 2 shipped; Phase 3 autonomy core landed**
— see [docs/llm-wiki](./docs/llm-wiki/).

## Install

```text
/plugin marketplace add allada-homelab/public-skills
/plugin install llm-wiki@public-skills
/reload-plugins
```

(During local development you can `marketplace add` a path to this repo instead of the slug.)
Then run `/llm-wiki:init` to create a bundle and `/llm-wiki:capture` to add the first concept.

## Repository layout

```text
public-skills/
├── .claude-plugin/marketplace.json   # marketplace manifest (this repo is the marketplace)
├── plugins/
│   └── llm-wiki/                      # the plugin (manifest, commands, skill, scripts)
├── llm-wiki/                          # this repo's own OKF bundle (dogfood + living example)
└── docs/llm-wiki/                     # product/phasing/per-phase plans + reference/ (OKF spec/blog, CC plugin system)
```

## Development

No build step or external dependencies — the plugin scripts are Python 3 stdlib only.

- **Run the test corpora** (Doctor conformance, the `bundle_ops` golden engine, and the hooks):
  ```text
  bash plugins/llm-wiki/scripts/fixtures/run_fixtures.sh       # pass=15 fail=0 skip=0
  bash plugins/llm-wiki/scripts/ops_fixtures/run_ops.sh        # pass=13 fail=0
  bash plugins/llm-wiki/scripts/hook_fixtures/run_hooks.sh     # pass=26 fail=0
  ```
- **Validate any bundle** against OKF v0.1:
  ```text
  python3 plugins/llm-wiki/scripts/doctor.py <bundle-dir> --mode strict
  ```

## License

[MIT](./LICENSE).
