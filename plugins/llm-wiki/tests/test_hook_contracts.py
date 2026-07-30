import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from job_state import JobController  # noqa: E402


class HookContractTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        self.project.mkdir()
        self.bundle = self.project / "llm-wiki"

    def run_hook(self, script_name, event):
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(self.project)
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script_name)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            cwd=self.project,
            env=env,
            timeout=10,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"{script_name} exited {proc.returncode}: {proc.stderr}",
        )
        return proc

    def create_bundle(self):
        self.bundle.mkdir()
        (self.bundle / "index.md").write_text(
            '---\nokf_version: "0.2"\n---\n# Knowledge\n\n'
            "## Concepts\n\n_No concepts yet._\n",
            encoding="utf-8",
        )

    def test_session_start_no_wiki_only_announces_on_startup(self):
        startup = self.run_hook(
            "hook_session_start.py",
            {
                "hook_event_name": "SessionStart",
                "source": "startup",
                "session_id": "session-startup",
                "cwd": str(self.project),
            },
        )
        payload = json.loads(startup.stdout)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        self.assertIn("No knowledge bundle", output["additionalContext"])

        resume = self.run_hook(
            "hook_session_start.py",
            {
                "hook_event_name": "SessionStart",
                "source": "resume",
                "session_id": "session-resume",
                "cwd": str(self.project),
            },
        )
        self.assertEqual(resume.stdout, "")

    def test_user_prompt_fallback_is_once_per_session(self):
        self.create_bundle()
        event = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "consult-session",
            "cwd": str(self.project),
            "prompt": "How does this repository work?",
        }

        first = self.run_hook("hook_user_prompt.py", event)
        payload = json.loads(first.stdout)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "UserPromptSubmit")
        self.assertIn("No strong metadata match", output["additionalContext"])

        second = self.run_hook("hook_user_prompt.py", event)
        self.assertEqual(second.stdout, "")

        other_session = self.run_hook(
            "hook_user_prompt.py", {**event, "session_id": "other-session"}
        )
        self.assertIn("No strong metadata match", other_session.stdout)

    def test_recursive_candidates_emit_on_every_matching_prompt(self):
        self.create_bundle()
        section = self.bundle / "auth"
        section.mkdir()
        (section / "index.md").write_text(
            "# Auth\n\n## Concepts\n\n"
            "* [Token rotation](./token-rotation.md) — Rotate signing keys safely.\n",
            encoding="utf-8",
        )
        (self.bundle / "index.md").write_text(
            '---\nokf_version: "0.2"\n---\n# Knowledge\n\n## Concepts\n\n_No concepts yet._\n\n'
            "## Sections\n\n* [Auth](./auth/index.md)\n",
            encoding="utf-8",
        )
        event = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "candidate-session",
            "cwd": str(self.project),
            "prompt": "How do we handle token rotation?",
        }
        for _ in range(2):
            result = self.run_hook("hook_user_prompt.py", event)
            self.assertIn("candidate_envelope", result.stdout)
            self.assertIn("auth/token-rotation.md", result.stdout)
            self.assertLessEqual(len(result.stdout), 8000)

    def test_post_tool_marks_project_write_not_bundle_write_and_stop_blocks_once(self):
        self.create_bundle()
        session_id = "post-session"
        marker = self.bundle / ".llm-wiki" / f"capture-pending-{session_id}"
        self.run_hook(
            "hook_session_start.py",
            {
                "hook_event_name": "SessionStart",
                "source": "startup",
                "session_id": session_id,
                "cwd": str(self.project),
            },
        )

        inside_bundle = self.run_hook(
            "hook_post_tool.py",
            {
                "hook_event_name": "PostToolUse",
                "session_id": session_id,
                "cwd": str(self.project),
                "tool_name": "Write",
                "tool_input": {"file_path": str(self.bundle / "concept.md")},
            },
        )
        self.assertEqual(inside_bundle.stdout, "")
        self.assertFalse(marker.exists())

        source_path = self.project / "src" / "app.py"
        source_path.parent.mkdir()
        source_path.write_text("ENABLED = True\n", encoding="utf-8")
        outside_bundle = self.run_hook(
            "hook_post_tool.py",
            {
                "hook_event_name": "PostToolUse",
                "session_id": session_id,
                "cwd": str(self.project),
                "tool_name": "Write",
                "tool_input": {"file_path": str(source_path)},
            },
        )
        self.assertEqual(outside_bundle.stdout, "")
        self.assertEqual(marker.read_text(encoding="utf-8"), "1")

        stop_event = {
            "hook_event_name": "Stop",
            "session_id": session_id,
            "cwd": str(self.project),
            "stop_hook_active": False,
        }
        first_stop = self.run_hook("hook_stop.py", stop_event)
        decision = json.loads(first_stop.stdout)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("End-of-turn coprocessors", decision["reason"])
        self.assertFalse(marker.exists())

        second_stop = self.run_hook("hook_stop.py", stop_event)
        self.assertEqual(second_stop.stdout, "")

    def test_pre_tool_allows_outside_write_and_denies_bundle_secret(self):
        self.create_bundle()
        safe = self.run_hook(
            "hook_pre_write.py",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "pre-session",
                "cwd": str(self.project),
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(self.project / "src" / "safe.py"),
                    "content": "API_KEY = 'safe-placeholder'\n",
                },
            },
        )
        self.assertEqual(safe.stdout, "")

        synthetic_secret = "AKIA" + "1234567890ABCDEF"
        denied = self.run_hook(
            "hook_pre_write.py",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "pre-session",
                "cwd": str(self.project),
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(self.bundle / "credential.md"),
                    "content": synthetic_secret,
                },
            },
        )
        payload = json.loads(denied.stdout)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("secret guard blocked", output["permissionDecisionReason"])
        self.assertNotIn(synthetic_secret, output["permissionDecisionReason"])

    def test_scribe_bash_is_restricted_to_fixed_publication_pipeline(self):
        unsafe = self.run_hook(
            "hook_pre_bash.py",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "scribe-session",
                "cwd": str(self.project),
                "agent_type": "llm-wiki:wiki-capturer",
                "tool_name": "Bash",
                "tool_input": {"command": "python3 -c 'print(1)'"},
            },
        )
        self.assertEqual(
            json.loads(unsafe.stdout)["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        safe = self.run_hook(
            "hook_pre_bash.py",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "scribe-session",
                "cwd": str(self.project),
                "agent_type": "llm-wiki:wiki-capturer",
                "tool_name": "Bash",
                "tool_input": {
                    "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/publication.py" '
                               '"/tmp/request.json" "/tmp/prepared.md"'
                },
            },
        )
        self.assertEqual(safe.stdout, "")
        main_agent = self.run_hook(
            "hook_pre_bash.py",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "scribe-session",
                "cwd": str(self.project),
                "tool_name": "Bash",
                "tool_input": {"command": "python3 -c 'print(1)'"},
            },
        )
        self.assertEqual(main_agent.stdout, "")

        staged = self.run_hook(
            "hook_pre_write.py",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "scribe-session",
                "cwd": str(self.project),
                "agent_type": "llm-wiki:wiki-capturer",
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/llm-wiki-request.json", "content": "{}"},
            },
        )
        self.assertEqual(staged.stdout, "")
        source_write = self.run_hook(
            "hook_pre_write.py",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "scribe-session",
                "cwd": str(self.project),
                "agent_type": "llm-wiki:wiki-capturer",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(self.project / "src" / "owned.py"),
                    "content": "OWNED = True\n",
                },
            },
        )
        self.assertEqual(
            json.loads(source_write.stdout)["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_read_policy_limits_only_llm_wiki_reasoning_agents(self):
        source = self.project / "src" / "safe.py"
        source.parent.mkdir()
        source.write_text("SAFE = True\n", encoding="utf-8")
        secret = self.project / ".env"
        secret.write_text("TOKEN=not-a-real-token\n", encoding="utf-8")
        base = {
            "hook_event_name": "PreToolUse",
            "cwd": str(self.project),
            "tool_name": "Read",
            "agent_type": "llm-wiki:wiki-verifier",
        }

        allowed = self.run_hook(
            "hook_pre_read.py", {**base, "tool_input": {"file_path": str(source)}}
        )
        self.assertEqual(allowed.stdout, "")

        for target in (secret, self.project.parent / "outside.txt"):
            with self.subTest(target=target):
                denied = self.run_hook(
                    "hook_pre_read.py", {**base, "tool_input": {"file_path": str(target)}}
                )
                output = json.loads(denied.stdout)["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")

        main_session = self.run_hook(
            "hook_pre_read.py",
            {
                **base,
                "agent_type": "",
                "tool_input": {"file_path": str(secret)},
            },
        )
        self.assertEqual(main_session.stdout, "")

        broad = self.run_hook(
            "hook_pre_read.py",
            {
                **base,
                "tool_name": "Grep",
                "tool_input": {"path": str(self.project), "pattern": "TOKEN"},
            },
        )
        self.assertEqual(
            json.loads(broad.stdout)["hookSpecificOutput"]["permissionDecision"], "deny"
        )

        narrowed = self.run_hook(
            "hook_pre_read.py",
            {
                **base,
                "tool_name": "Glob",
                "tool_input": {"path": str(self.project), "pattern": "src/**/*.py"},
            },
        )
        self.assertEqual(narrowed.stdout, "")

    def test_researcher_read_is_limited_to_controller_manifest(self):
        self.create_bundle()
        allowed_path = self.project / "src" / "allowed.py"
        denied_path = self.project / "src" / "other.py"
        allowed_path.parent.mkdir()
        allowed_path.write_text("ALLOWED = True\n", encoding="utf-8")
        denied_path.write_text("OTHER = True\n", encoding="utf-8")
        controller = JobController(self.project, "research-session")
        job, _ = controller.propose(
            "gap", "user_prompt", "gap:read-scope",
            {"calls": 1, "turns": 24, "seconds": 120, "descendants": 0},
            "worker",
        )
        self.assertTrue(controller.authorize(job["packet_id"], [allowed_path]))
        self.assertTrue(controller.start(job["packet_id"]))
        base = {
            "hook_event_name": "PreToolUse",
            "session_id": "research-session",
            "cwd": str(self.project),
            "agent_type": "llm-wiki:wiki-researcher",
            "tool_name": "Read",
        }
        allowed = self.run_hook(
            "hook_pre_read.py", {**base, "tool_input": {"file_path": str(allowed_path)}}
        )
        self.assertEqual(allowed.stdout, "")
        denied = self.run_hook(
            "hook_pre_read.py", {**base, "tool_input": {"file_path": str(denied_path)}}
        )
        self.assertEqual(
            json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"], "deny"
        )


if __name__ == "__main__":
    unittest.main()
