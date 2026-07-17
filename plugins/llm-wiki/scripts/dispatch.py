"""Select the controller job that authorizes a protected Agent or Skill dispatch."""

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
    return matches[0] if len(matches) == 1 else None
