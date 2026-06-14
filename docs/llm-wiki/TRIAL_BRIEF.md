# llm-wiki — real-world trial brief

Use this when trying `llm-wiki` in another repo before scoping Phase 2. The goal is to leave behind
**analyzable artifacts** (a friction log + the repo's own bundle), since a separate Claude Code session
can't be observed live.

## 1. Paste this into the other repo's Claude Code (at the start)

> I'm trialing my `llm-wiki` Claude Code plugin here as a real-world test before building its next
> phase. Please:
>
> 1. **Use it naturally** as we work — when we learn something worth keeping (a decision, gotcha,
>    convention, how something works), capture it to the wiki. Notice whether you reach for it on your
>    own vs. only when I ask.
> 2. **Keep a running log** at `LLM_WIKI_TRIAL.md`: each entry = what command/skill fired, whether the
>    `llm-wiki:wiki` skill **auto-activated** (or you only used it because I said so), what felt good,
>    what was friction, and any **Doctor errors or secret-scan hits pasted verbatim**.
> 3. The bundle defaults to `./llm-wiki/`. Run `/reload-plugins` first; if `/llm-wiki:init` still
>    targets the repo root instead of `./llm-wiki/`, run `/plugin update llm-wiki` then reload.
> 4. **At session end**, append a short verdict: did the wiki make you faster/more accurate? What one
>    thing would you change?

## 2. What to watch for during the trial

- Does the `llm-wiki:wiki` skill auto-activate on natural phrasing ("save this to the wiki") with no
  slash command?
- Are captured concepts genuinely useful when you `query` them back in a later session?
- Friction: is `capture` too heavyweight? confirm-first too chatty? is `query` grounding good? is the
  gap flag helpful?
- Any content that trips the Doctor's frontmatter parser (odd `tags`, nested YAML) or false-positives
  in the secret scanner.

## 3. Bring back for analysis

Return to the `public-skills` session and provide:

1. **The other repo's absolute path** — Claude Code transcripts live at
   `~/.claude/projects/<absolute-path-with-slashes-as-dashes>/*.jsonl`, so the path lets the analysis
   read the *actual* tool calls (every `/llm-wiki:*` invocation, when the skill loaded, Doctor exit
   codes, confirm-first prompts) — unfiltered ground truth.
2. A pointer to **`LLM_WIKI_TRIAL.md`** and the repo's **`./llm-wiki/`** bundle.

The analysis will synthesize: where the skill failed to auto-activate, capture friction, parser/secret
false positives, and "wished-it-did" gaps → a prioritized Phase 2 input (which may reshuffle Phase 2).

> **Caveat:** one repo's trial is a single data point — strong for finding friction and bugs, weaker
> for the "makes sessions smarter over time" claim (that needs repeated sessions). Don't over-index on
> the first sitting; the friction log is the high-value output.
