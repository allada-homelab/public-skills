"""Session-local causal job controller for bounded llm-wiki autonomous work."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import tempfile
import time

import _hook_common
from packet_contracts import SCHEMA, VERSION, validate_packet


TERMINAL = frozenset({"completed", "blocked", "failed", "cancelled", "stale"})
ROLES = frozenset({"worker", "synthesizer", "publisher"})
RESULT_KINDS = {
    "worker": "evidence_packet",
    "synthesizer": "context_capsule",
    "publisher": "publication_request",
}
_BUDGET_FIELDS = ("calls", "turns", "seconds", "descendants")


def repository_id(project):
    real = os.path.realpath(project)
    label = os.path.basename(real) or "repository"
    return "%s-%s" % (label, hashlib.sha256(real.encode("utf-8")).hexdigest()[:12])


def causal_run_id(repository, worktree, session_id):
    value = "%s\0%s\0%s" % (repository, os.path.realpath(worktree), session_id or "__nosession__")
    return "run-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def deterministic_job_id(run_id, idempotency_key):
    value = "%s\0%s" % (run_id, idempotency_key)
    return "job-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def public_job_record(packet):
    """Strip controller bookkeeping while preserving a valid, dispatchable job packet."""
    payload = packet["payload"]
    public_payload = {
        key: payload[key]
        for key in (
            "feature", "origin", "session_id", "depth", "idempotency_key", "budgets", "state",
            "role", "deadline", "allow_descendants", "allowed_features",
        )
        if key in payload
    }
    if "parent_id" in payload:
        public_payload["parent_id"] = payload["parent_id"]
    public = {**packet, "payload": public_payload}
    validate_packet(public, "job_record")
    return public


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


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError, UnicodeDecodeError):
        return default
    return value


class JobController:
    def __init__(self, project, session_id=None, now=None):
        self.project = os.path.realpath(project)
        self.session_id = str(session_id or "__nosession__")
        self.repository = repository_id(self.project)
        self.run_id = causal_run_id(self.repository, self.project, self.session_id)
        self.root = _hook_common.session_state_dir(self.project, self.session_id)
        self.jobs_dir = os.path.join(self.root, "jobs")
        self.claims_dir = os.path.join(self.root, "claims")
        self.controller_path = os.path.join(self.root, "controller.json")
        self.lock_path = os.path.join(self.root, "controller.lock")
        self.now = now or time.time
        _hook_common.ensure_bundle_gitignore(_hook_common.bundle_root(self.project))

    @contextmanager
    def _lock(self):
        os.makedirs(self.root, exist_ok=True)
        with open(self.lock_path, "a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield

    def _controller(self):
        return _read_json(self.controller_path, {
            "run_id": self.run_id,
            "reserved": {field: 0 for field in _BUDGET_FIELDS},
            "last_feature_at": {},
        })

    def _job_path(self, job_id):
        return os.path.join(self.jobs_dir, job_id + ".json")

    def get(self, job_id):
        return _read_json(self._job_path(job_id))

    def authorize(self, job_id, read_paths, **metadata):
        """Attach code-owned read authorization/request identity before a pending job dispatch."""
        with self._lock():
            packet = self.get(job_id)
            if packet is None or packet["payload"]["state"] != "pending":
                return False
            paths = sorted(set(os.path.realpath(path) for path in read_paths))
            packet["payload"]["authorization"] = {"read_paths": paths, **metadata}
            self._write_job(packet)
            return True

    def authorized_reads(self, feature):
        """Return the union of exact paths for currently running jobs of one agent feature."""
        paths = set()
        try:
            names = os.listdir(self.jobs_dir)
        except OSError:
            return paths
        for name in names:
            if not name.endswith(".json"):
                continue
            packet = _read_json(os.path.join(self.jobs_dir, name))
            payload = packet.get("payload", {}) if isinstance(packet, dict) else {}
            if payload.get("feature") != feature or payload.get("state") != "running":
                continue
            authorization = payload.get("authorization", {})
            paths.update(authorization.get("read_paths", ()))
        return paths

    def _claim_path(self, idempotency_key):
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return os.path.join(self.claims_dir, digest + ".json")

    def _write_job(self, packet):
        validate_packet(packet, "job_record")
        _atomic_json(self._job_path(packet["packet_id"]), packet)

    def _release_root_reservation(self, packet):
        if packet["payload"].get("parent_id") or packet["payload"].get("reservation_released"):
            return
        controller = self._controller()
        for field in ("calls", "turns", "seconds"):
            controller["reserved"][field] = max(
                0, controller["reserved"].get(field, 0) - packet["payload"]["budgets"][field]
            )
        packet["payload"]["reservation_released"] = True
        _atomic_json(self.controller_path, controller)

    def _blocked(self, job_id, feature, origin, key, budgets, role, reason, parent_id, depth):
        return self._packet(
            job_id, feature, origin, key, budgets, role, "blocked", parent_id, depth,
            reason=reason,
        )

    def _packet(
        self, job_id, feature, origin, key, budgets, role, state, parent_id, depth, **extra
    ):
        payload = {
            "feature": feature,
            "origin": origin,
            "session_id": self.session_id,
            "depth": depth,
            "idempotency_key": key,
            "budgets": dict(budgets),
            "state": state,
            "role": role,
            "created_at": int(self.now()),
            "deadline": int(self.now()) + budgets["seconds"],
            "attempts_started": 0,
            "usage": {"calls": 0, "turns": 0, "seconds": 0},
            "allow_descendants": bool(extra.pop("allow_descendants", False)),
            "allowed_features": list(extra.pop("allowed_features", ())),
            "child_reservations": {field: 0 for field in _BUDGET_FIELDS},
        }
        if parent_id:
            payload["parent_id"] = parent_id
        payload.update(extra)
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "kind": "job_record",
            "packet_id": job_id,
            "run_id": self.run_id,
            "payload": payload,
        }

    def propose(
        self,
        feature,
        origin,
        idempotency_key,
        budgets,
        role,
        parent_id=None,
        allow_descendants=False,
        allowed_features=(),
    ):
        """Atomically reserve one unique job; duplicate keys return the existing packet."""
        feature = str(feature).lower()
        if role not in ROLES:
            raise ValueError("unsupported job role")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty")
        normalized = {}
        for field in _BUDGET_FIELDS:
            value = budgets.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("budget %s must be a non-negative integer" % field)
            normalized[field] = value
        job_id = deterministic_job_id(self.run_id, idempotency_key)
        claim_path = self._claim_path(idempotency_key)

        with self._lock():
            claim = _read_json(claim_path)
            if isinstance(claim, dict):
                existing = self.get(claim.get("job_id", ""))
                if existing is not None:
                    return existing, True

            settings = _hook_common.load_settings(self.project)
            controller = self._controller()
            parent = self.get(parent_id) if parent_id else None
            depth = parent["payload"]["depth"] + 1 if parent else 0
            reason = None
            if origin != "user_command" and settings["autonomy"] == "off":
                reason = "global autonomy kill switch is off"
            elif origin != "user_command" and feature in settings["autonomy_disabled"]:
                reason = "feature is disabled"
            elif parent_id and parent is None:
                reason = "parent job is missing"
            elif parent and parent["payload"]["state"] != "running" and not (
                origin == "system:planner" and parent["payload"]["state"] == "pending"
            ):
                reason = "parent job is not running"
            elif parent and not parent["payload"].get("allow_descendants"):
                reason = "parent does not allow descendants"
            elif parent and feature not in parent["payload"].get("allowed_features", []):
                reason = "feature is not allowlisted by parent"
            elif origin.startswith("plugin:") and parent is None:
                reason = "plugin-origin jobs require an allowlisting parent"
            elif depth > settings["autonomy_max_depth"]:
                reason = "maximum job depth exceeded"

            if reason is None and parent:
                reserved = parent["payload"].get("child_reservations", {})
                if reserved.get("descendants", 0) + 1 > parent["payload"]["budgets"]["descendants"]:
                    reason = "parent descendant budget exhausted"
                else:
                    for field in ("calls", "turns", "seconds"):
                        if reserved.get(field, 0) + normalized[field] > parent["payload"]["budgets"][field]:
                            reason = "parent %s budget exhausted" % field
                            break
            elif reason is None:
                limits = {
                    "calls": settings["autonomy_max_calls"],
                    "turns": settings["autonomy_max_turns"],
                    "seconds": settings["autonomy_max_seconds"],
                    "descendants": settings["autonomy_max_descendants"],
                }
                if normalized["descendants"] > limits["descendants"]:
                    reason = "session descendants budget exhausted"
                for field in ("calls", "turns", "seconds"):
                    if controller["reserved"].get(field, 0) + normalized[field] > limits[field]:
                        reason = "session %s budget exhausted" % field
                        break

            cooldown = settings["autonomy_cooldowns"].get(feature, 0)
            last_at = controller["last_feature_at"].get(feature)
            if reason is None and cooldown and last_at is not None and self.now() - last_at < cooldown:
                reason = "feature cooldown is active"

            if reason:
                packet = self._blocked(
                    job_id, feature, origin, idempotency_key, normalized, role, reason, parent_id, depth
                )
            else:
                packet = self._packet(
                    job_id,
                    feature,
                    origin,
                    idempotency_key,
                    normalized,
                    role,
                    "pending",
                    parent_id,
                    depth,
                    allow_descendants=allow_descendants,
                    allowed_features=allowed_features,
                )
                if parent:
                    reservations = parent["payload"]["child_reservations"]
                    for field in ("calls", "turns", "seconds"):
                        reservations[field] += normalized[field]
                    reservations["descendants"] += 1
                    self._write_job(parent)
                else:
                    for field in ("calls", "turns", "seconds"):
                        controller["reserved"][field] += normalized[field]
                controller["last_feature_at"][feature] = self.now()
                _atomic_json(self.controller_path, controller)

            self._write_job(packet)
            os.makedirs(self.claims_dir, exist_ok=True)
            try:
                fd = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump({"job_id": job_id}, handle, separators=(",", ":"))
            except FileExistsError:
                pass
            return packet, False

    def _ancestors_live(self, packet):
        parent_id = packet["payload"].get("parent_id")
        while parent_id:
            parent = self.get(parent_id)
            # A pre-issued child may start after its parent has successfully synthesized its result;
            # cancelled/failed/stale ancestry still invalidates it.
            if parent is None or parent["payload"]["state"] not in ("running", "completed"):
                return False
            parent_id = parent["payload"].get("parent_id")
        return True

    def start(self, job_id):
        with self._lock():
            packet = self.get(job_id)
            if packet is None or packet["payload"]["state"] != "pending":
                return False
            if packet["payload"]["deadline"] < self.now() or not self._ancestors_live(packet):
                packet["payload"]["state"] = "stale" if packet["payload"]["deadline"] < self.now() else "cancelled"
                self._release_root_reservation(packet)
                self._write_job(packet)
                return False
            packet["payload"]["state"] = "running"
            packet["payload"]["attempts_started"] = 1
            self._write_job(packet)
            return True

    def cancel(self, job_id):
        with self._lock():
            packet = self.get(job_id)
            if packet is None or packet["payload"]["state"] in TERMINAL:
                return False
            packet["payload"]["state"] = "cancelled"
            self._release_root_reservation(packet)
            self._write_job(packet)
            return True

    def cancel_tree(self, job_id):
        """Cancel a live root and every pending/running descendant, even if the root completed."""
        with self._lock():
            jobs = []
            try:
                names = os.listdir(self.jobs_dir)
            except OSError:
                names = []
            for name in names:
                if name.endswith(".json"):
                    packet = _read_json(os.path.join(self.jobs_dir, name))
                    if isinstance(packet, dict):
                        jobs.append(packet)
            descendants, frontier = set(), {job_id}
            while frontier:
                parent = frontier.pop()
                children = {
                    packet["packet_id"] for packet in jobs
                    if packet.get("payload", {}).get("parent_id") == parent
                } - descendants
                descendants.update(children)
                frontier.update(children)
            changed = False
            for packet in jobs:
                if packet["packet_id"] not in descendants | {job_id}:
                    continue
                if packet["payload"]["state"] not in TERMINAL:
                    packet["payload"]["state"] = "cancelled"
                    self._release_root_reservation(packet)
                    self._write_job(packet)
                    changed = True
            return changed

    def attempt_failed(self, job_id, reason):
        with self._lock():
            packet = self.get(job_id)
            if packet is None or packet["payload"]["state"] != "running":
                return False
            failures = packet["payload"].setdefault("attempt_failures", [])
            failures.append(str(reason)[:500])
            if packet["payload"]["attempts_started"] < 2:
                packet["payload"]["attempts_started"] += 1
                self._write_job(packet)
                return True
            packet["payload"]["state"] = "failed"
            self._release_root_reservation(packet)
            self._write_job(packet)
            return False

    def accept_result(self, job_id, result_kind, usage=None):
        with self._lock():
            packet = self.get(job_id)
            if packet is None or packet["payload"]["state"] != "running":
                return False
            if packet["payload"]["deadline"] < self.now() or not self._ancestors_live(packet):
                packet["payload"]["state"] = "stale"
                self._release_root_reservation(packet)
                self._write_job(packet)
                return False
            if RESULT_KINDS[packet["payload"]["role"]] != result_kind:
                return False
            if usage:
                for field in ("calls", "turns", "seconds"):
                    value = usage.get(field, 0)
                    if not isinstance(value, int) or value < 0 or value > packet["payload"]["budgets"][field]:
                        return False
                packet["payload"]["usage"] = dict(usage)
            packet["payload"]["state"] = "completed"
            self._release_root_reservation(packet)
            self._write_job(packet)
            return True
