"""Session-local changed-path ledger and immutable evidence-packet finalizer."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile

import _hook_common
from job_state import JobController, repository_id
from packet_contracts import SCHEMA, VERSION, canonical_json, validate_packet


MAX_PATHS = 512


def _run_git(project, args):
    try:
        proc = subprocess.run(
            ["git", "-C", project] + list(args),
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _git_text(project, args, fallback):
    raw = _run_git(project, args)
    if raw is None:
        return fallback
    value = raw.decode("utf-8", "replace").strip()
    return value or fallback


def _git_paths(project, args):
    raw = _run_git(project, args)
    if raw is None:
        return set()
    return {
        value.decode("utf-8", "surrogateescape").replace(os.sep, "/")
        for value in raw.split(b"\0")
        if value
    }


def _dirty_paths(project):
    paths = set()
    paths.update(_git_paths(project, ["diff", "--name-only", "-z"]))
    paths.update(_git_paths(project, ["diff", "--cached", "--name-only", "-z"]))
    paths.update(_git_paths(project, ["ls-files", "--others", "--exclude-standard", "-z"]))
    return paths


def _file_hash(project, relpath):
    path = os.path.join(project, relpath)
    if not os.path.lexists(path):
        return None
    digest = hashlib.sha256()
    try:
        if os.path.islink(path):
            digest.update(os.readlink(path).encode("utf-8", "surrogateescape"))
        else:
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
    except OSError:
        return None
    return "sha256:" + digest.hexdigest()


def _base_hash(project, head, relpath):
    if head in ("unknown", "unborn"):
        return None
    raw = _run_git(project, ["show", "%s:%s" % (head, relpath)])
    return "sha256:" + hashlib.sha256(raw).hexdigest() if raw is not None else None


def _atomic_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, UnicodeDecodeError):
        return default


class EvidenceLedger:
    def __init__(self, project, session_id=None):
        self.project = os.path.realpath(project)
        self.session_id = str(session_id or "__nosession__")
        self.root = _hook_common.session_state_dir(self.project, self.session_id)
        self.baseline_path = os.path.join(self.root, "baseline.json")
        self.ledger_path = os.path.join(self.root, "ledger.json")
        self.lock_path = os.path.join(self.root, "ledger.lock")
        self.evidence_dir = os.path.join(self.root, "evidence")

    def _excluded(self, relpath):
        bundle_rel = os.path.relpath(
            os.path.realpath(_hook_common.bundle_root(self.project)), self.project
        ).replace(os.sep, "/")
        return (
            relpath == bundle_rel
            or relpath.startswith(bundle_rel.rstrip("/") + "/")
            or ".llm-wiki" in relpath.split("/")
            or relpath == ".claude/llm-wiki.local.md"
        )

    @contextmanager
    def _lock(self):
        os.makedirs(self.root, exist_ok=True)
        with open(self.lock_path, "a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield

    def initialize(self):
        """Snapshot dirty hashes once; compact/resume SessionStart events cannot reset the baseline."""
        with self._lock():
            existing = _read_json(self.baseline_path, None)
            if existing is not None:
                return existing
            dirty = sorted(path for path in _dirty_paths(self.project) if not self._excluded(path))
            selected = dirty[:MAX_PATHS]
            controller = JobController(self.project, self.session_id)
            baseline = {
                "repository": repository_id(self.project),
                "worktree": self.project,
                "branch": _git_text(self.project, ["branch", "--show-current"], "detached"),
                "base_head": _git_text(self.project, ["rev-parse", "HEAD"], "unborn"),
                "session_id": self.session_id,
                "run_id": controller.run_id,
                "dirty_hashes": {path: _file_hash(self.project, path) for path in selected},
                "dirty_truncated": len(dirty) > MAX_PATHS,
            }
            _atomic_json(self.baseline_path, baseline)
            _atomic_json(self.ledger_path, {"observed": {}, "truncated": False})
            return baseline

    def _normalize_event_path(self, event):
        fp = _hook_common.event_file_path(event)
        if fp is None:
            return None
        real = os.path.realpath(fp)
        if not _hook_common.under(real, self.project):
            return None
        relpath = os.path.relpath(real, self.project).replace(os.sep, "/")
        if self._excluded(relpath):
            return None
        return relpath

    def record_tool_event(self, event):
        if event.get("tool_name") not in ("Write", "Edit"):
            return False
        agent_type = event.get("agent_type")
        if isinstance(agent_type, str) and agent_type.startswith("llm-wiki:"):
            return False
        relpath = self._normalize_event_path(event)
        if relpath is None:
            return False
        self.initialize()
        with self._lock():
            ledger = _read_json(self.ledger_path, {"observed": {}, "truncated": False})
            observed = ledger["observed"]
            if relpath not in observed and len(observed) >= MAX_PATHS:
                ledger["truncated"] = True
                _atomic_json(self.ledger_path, ledger)
                return False
            source = "edit" if event.get("tool_name") == "Edit" else "write"
            if observed.get(relpath) != "edit":
                observed[relpath] = source
            _atomic_json(self.ledger_path, ledger)
            return True

    def finalize(self):
        baseline = self.initialize()
        with self._lock():
            ledger = _read_json(self.ledger_path, {"observed": {}, "truncated": False})
            current_head = _git_text(self.project, ["rev-parse", "HEAD"], "unborn")
            dirty_now = _dirty_paths(self.project)
            committed = set()
            if baseline["base_head"] not in ("unknown", "unborn") and current_head != baseline["base_head"]:
                committed = _git_paths(
                    self.project,
                    ["diff", "--name-only", "-z", baseline["base_head"], current_head],
                )
            candidates = sorted(
                path for path in (dirty_now | committed | set(ledger["observed"]))
                if not self._excluded(path)
            )
            changed = []
            for relpath in candidates[:MAX_PATHS]:
                if relpath in baseline["dirty_hashes"]:
                    before = baseline["dirty_hashes"][relpath]
                else:
                    before = _base_hash(self.project, baseline["base_head"], relpath)
                after = _file_hash(self.project, relpath)
                # Comparing bytes, rather than treating a clean git status as proof of reversion,
                # also preserves observed writes in repositories without an initialized git history.
                if before == after or (before is None and after is None):
                    continue
                changed.append({
                    "path": relpath,
                    "before_sha256": before,
                    "after_sha256": after,
                    "source": ledger["observed"].get(relpath, "git_delta"),
                })

            revision_input = {
                "repository": baseline["repository"],
                "worktree": self.project,
                "base_head": baseline["base_head"],
                "current_head": current_head,
                "branch": _git_text(self.project, ["branch", "--show-current"], baseline["branch"]),
                "changed_paths": changed,
            }
            encoded_revision = json.dumps(
                revision_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            revision = hashlib.sha256(encoded_revision.encode("utf-8")).hexdigest()
            packet = {
                "schema": SCHEMA,
                "version": VERSION,
                "kind": "evidence_packet",
                "packet_id": "evidence-" + revision[:20],
                "run_id": baseline["run_id"],
                "payload": {
                    "repository": baseline["repository"],
                    "worktree": self.project,
                    "branch": revision_input["branch"],
                    "base_head": baseline["base_head"],
                    "session_id": self.session_id,
                    "revision": revision,
                    "changed_paths": changed,
                    "current_head": current_head,
                    "baseline_truncated": baseline["dirty_truncated"],
                    "ledger_truncated": ledger["truncated"] or len(candidates) > MAX_PATHS,
                },
            }
            validate_packet(packet, "evidence_packet")
            os.makedirs(self.evidence_dir, exist_ok=True)
            path = os.path.join(self.evidence_dir, revision + ".json")
            if not os.path.exists(path):
                try:
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        handle.write(canonical_json(packet))
                except FileExistsError:
                    pass
            _atomic_json(os.path.join(self.root, "latest-evidence.json"), {
                "packet_id": packet["packet_id"], "revision": revision, "path": path
            })
            return packet, path
