"""Offline contract tests for the Claude Code runtime surfaces in ticket 001."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
AGENT_EXPECTATIONS = {
    "wiki-capturer.md": {
        "model": "sonnet",
        "effort": "medium",
        "maxTurns": "12",
        "background": "true",
    },
    "wiki-verifier.md": {
        "model": "sonnet",
        "effort": "medium",
        "maxTurns": "8",
    },
    "wiki-explorer.md": {
        "model": "sonnet",
        "effort": "high",
        "maxTurns": "32",
    },
    "wiki-compiler.md": {
        "model": "sonnet",
        "effort": "medium",
        "maxTurns": "10",
    },
    "wiki-glimmer.md": {
        "model": "sonnet",
        "effort": "low",
        "maxTurns": "4",
    },
    "wiki-archaeologist.md": {
        "model": "sonnet",
        "effort": "high",
        "maxTurns": "24",
    },
    "wiki-evidence-worker.md": {
        "model": "sonnet",
        "effort": "low",
        "maxTurns": "6",
    },
    "wiki-sentinel.md": {
        "model": "sonnet",
        "effort": "medium",
        "maxTurns": "8",
        "background": "true",
    },
    "wiki-researcher.md": {
        "model": "sonnet",
        "effort": "high",
        "maxTurns": "24",
        "background": "true",
    },
}
UNSUPPORTED_PLUGIN_AGENT_FIELDS = {"hooks", "mcpServers", "permissionMode", "timeout"}
LIVE_TEXT_PATHS = (
    PLUGIN_ROOT / "agents",
    PLUGIN_ROOT / "commands",
    PLUGIN_ROOT / "hooks",
    PLUGIN_ROOT / "scripts",
    PLUGIN_ROOT / "skills",
    PLUGIN_ROOT / "README.md",
)


def _frontmatter(path: Path) -> dict[str, str]:
    """Parse the top-level scalar keys used by agent/command frontmatter."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError(f"{path} has no YAML frontmatter")

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return fields
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s*(.*))?$", line)
        if match:
            fields[match.group(1)] = (match.group(2) or "").strip()
    raise AssertionError(f"{path} has unterminated YAML frontmatter")


def _live_text_files() -> list[Path]:
    files: list[Path] = []
    for path in LIVE_TEXT_PATHS:
        if path.is_file():
            files.append(path)
            continue
        files.extend(
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file() and "__pycache__" not in candidate.parts
        )
    return sorted(files)


def _matches(pattern: str) -> list[str]:
    regex = re.compile(pattern)
    findings: list[str] = []
    for path in _live_text_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, 1):
            if regex.search(line):
                findings.append(f"{path.relative_to(PLUGIN_ROOT)}:{line_number}: {line.strip()}")
    return findings


class RuntimeContractTests(unittest.TestCase):
    def test_agent_runtime_frontmatter(self) -> None:
        for filename, expected in AGENT_EXPECTATIONS.items():
            with self.subTest(agent=filename):
                fields = _frontmatter(PLUGIN_ROOT / "agents" / filename)
                for key, value in expected.items():
                    self.assertEqual(fields.get(key), value, f"{filename}: {key}")

                unsupported = UNSUPPORTED_PLUGIN_AGENT_FIELDS.intersection(fields)
                self.assertEqual(unsupported, set(), f"{filename}: unsupported fields")

                if filename not in ("wiki-capturer.md", "wiki-sentinel.md", "wiki-researcher.md"):
                    self.assertNotIn(
                        "background",
                        fields,
                        f"{filename}: required-result agents must remain foreground-capable",
                    )

    def test_no_live_retired_tool_names(self) -> None:
        # Numbered work-item prose (for example, "Task 4") is not a tool reference.
        findings = _matches(r"\bMultiEdit\b|\bTask\b(?!\s+\d+(?:'s)?\b)")
        self.assertEqual(findings, [], "retired Claude Code tools remain:\n" + "\n".join(findings))

    def test_no_haiku_model_selection(self) -> None:
        findings = _matches(r"(?i)^\s*model:\s*haiku\s*$")
        self.assertEqual(findings, [], "live surface selects Haiku:\n" + "\n".join(findings))

    def test_commands_allow_agent_and_use_scoped_subagent_types(self) -> None:
        cases = {
            "query.md": "llm-wiki:wiki-verifier",
            "ingest.md": "llm-wiki:wiki-explorer",
        }
        for filename, scoped_agent in cases.items():
            with self.subTest(command=filename):
                path = PLUGIN_ROOT / "commands" / filename
                fields = _frontmatter(path)
                allowed_tools = fields.get("allowed-tools", "")
                self.assertRegex(
                    allowed_tools,
                    r"(?:^|[\s,])Agent(?:$|[\s,])",
                    f"{filename}: Agent missing from allowed-tools",
                )
                body = path.read_text(encoding="utf-8")
                self.assertRegex(
                    body,
                    rf"subagent_type\s*:\s*`?{re.escape(scoped_agent)}`?",
                    f"{filename}: missing scoped subagent_type {scoped_agent}",
                )

        ingestion_reference = (
            PLUGIN_ROOT / "skills" / "wiki" / "references" / "ingestion.md"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            ingestion_reference,
            r"subagent_type\s*:\s*`?llm-wiki:wiki-explorer`?",
        )

    def test_hooks_json_uses_current_write_tools(self) -> None:
        with (PLUGIN_ROOT / "hooks" / "hooks.json").open(encoding="utf-8") as handle:
            config = json.load(handle)

        hooks = config["hooks"]
        self.assertEqual(
            [entry.get("matcher") for entry in hooks["PreToolUse"]],
            ["Write|Edit", "Read|Grep|Glob", "Bash", "Agent|Skill"],
        )
        self.assertEqual(
            [entry.get("matcher") for entry in hooks["PostToolUse"]],
            ["Write|Edit", "Agent|Skill"],
        )

    def test_verifier_is_read_only_and_run_anchors_are_disabled(self) -> None:
        path = PLUGIN_ROOT / "agents" / "wiki-verifier.md"
        fields = _frontmatter(path)
        self.assertEqual(fields.get("tools"), "Read")
        body = path.read_text(encoding="utf-8")
        self.assertIn("couldn't-verify (run anchors disabled)", body)
        self.assertNotIn("self-heal", body.lower())

        researcher = _frontmatter(PLUGIN_ROOT / "agents" / "wiki-researcher.md")
        self.assertEqual(researcher.get("tools"), "Read")

    def test_recall_runs_in_a_forked_scoped_compiler(self) -> None:
        skills = {
            "recall": "llm-wiki:wiki-compiler",
            "recall-glimmer": "llm-wiki:wiki-glimmer",
            "recall-archaeologist": "llm-wiki:wiki-archaeologist",
        }
        for skill, agent in skills.items():
            path = PLUGIN_ROOT / "skills" / skill / "SKILL.md"
            fields = _frontmatter(path)
            self.assertEqual(fields.get("context"), "fork")
            self.assertEqual(fields.get("agent"), agent)
            body = path.read_text(encoding="utf-8")
            self.assertEqual(body.count("$ARGUMENTS"), 1)

        compiler = _frontmatter(PLUGIN_ROOT / "agents" / "wiki-compiler.md")
        self.assertEqual(compiler.get("tools"), "Read, Agent")
        self.assertNotIn("background", compiler)

    def test_manifest_json_is_valid(self) -> None:
        with (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").open(encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest.get("name"), "llm-wiki")
        self.assertIsInstance(manifest.get("version"), str)
        self.assertTrue(manifest["version"])


if __name__ == "__main__":
    unittest.main()
