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
| `/llm-wiki:capture` | Turn a finding from the current session into one conformant concept. |
| `/llm-wiki:explore` | Navigate the wiki via `index.md` progressive disclosure (read-only). |
| `/llm-wiki:query` | Answer a question grounded in the wiki, with citations and a gap flag. |
| `/llm-wiki:conform` | Run the Doctor and report conformance (read-only). |

Plus the `llm-wiki:wiki` skill (OKF authoring/reading knowledge). Status: **Phase 1 (MVP) shipped**
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
└── docs/llm-wiki/                     # product/phasing/Phase-1 plans + reference/ (OKF spec/blog, CC plugin system)
```

## Development

No build step or external dependencies — the plugin scripts are Python 3 stdlib only.

- **Run the Doctor test suite** (the conformance proof corpus):
  ```text
  bash plugins/llm-wiki/scripts/fixtures/run_fixtures.sh
  ```
- **Validate any bundle** against OKF v0.1:
  ```text
  python3 plugins/llm-wiki/scripts/doctor.py <bundle-dir> --mode strict
  ```

## License

[MIT](./LICENSE).
