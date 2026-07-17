"""Select the controller job that authorizes a protected Agent or Skill dispatch."""

import os
import re


_JOB_ID = re.compile(r"\bjob-[0-9a-f]{20}\b")
_TARGET_FEATURE = {
    "recall-glimmer": "recall",
    "recall": "recall",
    "recall-archaeologist": "recall",
    "wiki-glimmer": "recall",
    "wiki-compiler": "recall",
    "wiki-archaeologist": "recall",
    "wiki-evidence-worker": "parallel",
    "wiki-sentinel": "impact",
    "wiki-capturer": "scribe",
    "wiki-researcher": "gap",
    "wiki-explorer": "ingest_worker",
}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def target_name(event):
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    if event.get("tool_name") == "Agent":
        value = tool_input.get("subagent_type")
    elif event.get("tool_name") == "Skill":
        value = tool_input.get("skill") or tool_input.get("name")
    else:
        return None
    return value.rsplit(":", 1)[-1] if isinstance(value, str) else None


def _startable_fallback(controller, feature):
    """The unique startable (pending, unexpired, this-run) job of `feature` in the session store.

    The id-scan below is brittle in real use — the orchestrator may drop the envelope, rewrap a
    request path, or quote an older cycle's job id alongside the current one — and every one of
    those shapes used to dead-end in an opaque deny. Falling back to the store grants no new
    authority: the job was still controller-issued, feature-matched, budget-reserved, and
    session-scoped; this only resolves it by feature instead of requiring its id in the text.
    Ambiguity (two startable jobs of one feature) still returns None — never guess."""
    try:
        names = os.listdir(controller.jobs_dir)
    except OSError:
        return None
    live = []
    for name in names:
        if not name.endswith(".json"):
            continue
        packet = controller.get(name[:-len(".json")])
        if (
            packet is not None
            and packet.get("run_id") == controller.run_id
            and packet.get("payload", {}).get("feature") == feature
            and packet["payload"].get("state") == "pending"
            and packet["payload"].get("deadline", 0) >= controller.now()
        ):
            live.append(packet)
    return live[0] if len(live) == 1 else None


def select_job(controller, event):
    """Pick the unique job matching the dispatch target, ignoring nested pre-issued child records."""
    feature = _TARGET_FEATURE.get(target_name(event))
    if feature is None:
        return None
    ids = sorted(set(
        match
        for value in _strings(event.get("tool_input"))
        for match in _JOB_ID.findall(value)
    ))
    matches = []
    for job_id in ids:
        packet = controller.get(job_id)
        if (
            packet is not None
            and packet.get("run_id") == controller.run_id
            and packet.get("payload", {}).get("feature") == feature
        ):
            matches.append(packet)
    if len(matches) == 1:
        return matches[0]
    return _startable_fallback(controller, feature)
