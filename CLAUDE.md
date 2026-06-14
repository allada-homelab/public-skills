# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

Greenfield. As of the initial commit the repo contains only `README.md`, `LICENSE`
(MIT), and `source_docs/`. There is **no source code, build system, dependency
manifest, test suite, or linter yet** — so there are no build/lint/test commands to
run. Do not invent them. Expand this file (commands, architecture) as real structure
lands.

## Purpose

`public-skills` is the user's public Claude Code **marketplace** — a repository of their
own skills, plugins, and MCP servers for development use. (Marketplace structure is not
set up yet; it will be added as the repo grows.)

**Planned first effort (not started):** implementing Google's **Open Knowledge Format
(OKF)** as an "LLM wiki" for Claude Code, delivered as some combination of a plugin,
skill, and/or MCP server. Nothing is designed or implemented yet.

## source_docs/

Reference material gathered for this repo's work — not itself an OKF bundle:

- `okf_repo.md` — links to the OKF v0.1 spec, the `okf/` directory, and the
  `mdcode/demo` reference implementation in `GoogleCloudPlatform/knowledge-catalog`.
- `okf_blog.md` — full text of Google Cloud's OKF announcement (2026-06-12).
- `okf_spec.md` — distilled OKF v0.1 spec rules (reserved files, frontmatter,
  conformance, cross-linking, reference implementations).
- `claude_code_plugin_system.md` — how Claude Code marketplaces, plugins, skills, MCP
  servers, commands, hooks, and agents compose, and when to use each.

### OKF in one paragraph (context for work here)

OKF is a vendor-neutral spec for representing curated knowledge as **a directory of
markdown files with YAML frontmatter**. Each file is one "concept" (table, dataset,
metric, runbook, API, …) and the file path is the concept's identity. The only
required frontmatter field is `type`; other conventional fields are `title`,
`description`, `resource`, `tags`, and `timestamp`. Concepts cross-link via ordinary
markdown links, forming a graph richer than the directory tree. Two optional reserved
filenames: `index.md` (progressive disclosure as an agent walks the hierarchy) and
`log.md` (chronological change history). Producers and consumers are deliberately
independent — no SDK, account, or platform required to read or write a bundle.
