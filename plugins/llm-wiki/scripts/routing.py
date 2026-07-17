"""Deterministic Sonnet route and task-lens selection for candidate envelopes."""

import re


ROUTES = {
    "glimmer": "/llm-wiki:recall-glimmer",
    "oracle": "/llm-wiki:recall",
    "archaeologist": "/llm-wiki:recall-archaeologist",
}
LENSES = frozenset({"implementer", "debugger", "reviewer", "operator", "newcomer", "historian", "neutral"})

_EXPLICIT_LENS = re.compile(
    r"(?:--lens\s+|\blens\s*:\s*)(implementer|debugger|reviewer|operator|newcomer|historian|neutral)\b",
    re.IGNORECASE,
)
_LENS_TERMS = (
    ("debugger", ("bug", "debug", "error", "failure", "stack trace", "root cause", "regression")),
    ("reviewer", ("review", "pull request", "pr", "diff", "risk", "regression")),
    ("operator", ("deploy", "incident", "production", "rollback", "runbook", "on-call", "outage")),
    ("newcomer", ("explain", "overview", "onboard", "new to", "how does", "architecture")),
    ("historian", ("history", "historical", "why did", "decision", "tradeoff", "migration")),
    ("implementer", ("implement", "build", "add", "change", "refactor", "integrate")),
)
_DEEP_TERMS = (
    "history", "historical", "why", "tradeoff", "security", "safety", "migration", "deprecated",
    "root cause", "regression", "contradiction", "conflict",
)
_SYNTHESIS_TERMS = ("across", "compare", "end to end", "interaction", "multiple", "system")
_CONTRADICTION_TERMS = ("conflict", "contradiction", "deprecated", "migration", "superseded")


def _lens(prompt):
    explicit = _EXPLICIT_LENS.search(prompt)
    if explicit:
        return explicit.group(1).lower(), "explicit task lens"
    lowered = prompt.lower()
    for lens, terms in _LENS_TERMS:
        if any(_has_term(lowered, term) for term in terms):
            return lens, "task intent matched %s lens" % lens
    return "neutral", "no task-specific lens signal"


def _has_term(text, term):
    if " " in term or "-" in term:
        return term in text
    return re.search(r"\b%s\b" % re.escape(term), text) is not None


def select_route(prompt, candidates):
    """Return a stable route/lens record without a model call or identity inference."""
    lowered = prompt.lower()
    sections = {candidate.get("section_path", "") for candidate in candidates}
    metadata = " ".join(
        "%s %s" % (candidate.get("title", ""), candidate.get("description", ""))
        for candidate in candidates
    ).lower()
    deep = [term for term in _DEEP_TERMS if term in lowered]
    contradiction = [term for term in _CONTRADICTION_TERMS if term in metadata]
    synthesis = any(term in lowered for term in _SYNTHESIS_TERMS)

    if "history" in deep or "historical" in deep or contradiction:
        route = "archaeologist"
        reason = "history/contradiction signal"
    elif deep and len(sections) >= 2:
        route = "archaeologist"
        reason = "deep-reasoning intent across %d sections" % len(sections)
    elif len(candidates) <= 2 and len(sections) <= 1 and not synthesis:
        route = "glimmer"
        reason = "direct lookup with %d candidate(s) in one section" % len(candidates)
    else:
        route = "oracle"
        reason = "multi-concept synthesis across %d section(s)" % len(sections)

    lens, lens_reason = _lens(prompt)
    return {
        "route": route,
        "skill": ROUTES[route],
        "reason": reason,
        "lens": lens,
        "lens_reason": lens_reason,
        "candidate_count": len(candidates),
        "section_count": len(sections),
    }
