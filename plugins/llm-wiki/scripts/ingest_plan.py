#!/usr/bin/env python3
"""Mint controller-issued bounded explorer jobs for an explicit ingest command."""

import argparse
import hashlib
import json
import os
import sys

from gap import current_head
from job_state import JobController, public_job_record
from topology import plan_ingest_scopes, validate_section


def plan(repo, bundle, scope, session_id, into=None, project=None):
    units = plan_ingest_scopes(repo, scope, bundle)
    explicit = validate_section(into) if into else ""
    controller = JobController(project or os.environ.get("CLAUDE_PROJECT_DIR") or repo, session_id)
    digest = hashlib.sha256(
        json.dumps(
            {
                "head": current_head(repo),
                "scope": scope,
                "into": explicit,
                "units": [item["source_manifest_sha256"] for item in units],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]
    parent, duplicate = controller.propose(
        feature="ingest",
        origin="user_command",
        idempotency_key="ingest:" + digest,
        budgets={
            "calls": len(units),
            "turns": 32 * len(units),
            "seconds": 120 * len(units),
            "descendants": len(units),
        },
        role="synthesizer",
        allow_descendants=True,
        allowed_features=("ingest_worker",),
    )
    if parent["payload"]["state"] == "pending":
        controller.start(parent["packet_id"])
        parent = controller.get(parent["packet_id"])
    workers = []
    for unit in units:
        child, child_duplicate = controller.propose(
            feature="ingest_worker",
            origin="plugin:ingest",
            idempotency_key="%s:%s" % (parent["packet_id"], unit["scope_id"]),
            budgets={"calls": 1, "turns": 32, "seconds": 120, "descendants": 0},
            role="worker",
            parent_id=parent["packet_id"],
        )
        if child["payload"]["state"] in ("pending", "running"):
            if child["payload"]["state"] == "pending":
                controller.authorize(
                    child["packet_id"],
                    [os.path.join(os.path.realpath(repo), path) for path in unit["source_manifest"]],
                    scope_id=unit["scope_id"],
                    source_manifest_sha256=unit["source_manifest_sha256"],
                    repo_root=os.path.realpath(repo),
                )
                child = controller.get(child["packet_id"])
            workers.append({**unit, "job": public_job_record(child), "duplicate": child_duplicate})
    return {
        "parent_job": public_job_record(parent),
        "duplicate": duplicate,
        "repository": os.path.realpath(repo),
        "bundle_root": os.path.realpath(bundle),
        "revision": current_head(repo),
        "scope": scope,
        "into": explicit,
        "workers": workers,
    }


def main(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    planner = subparsers.add_parser("plan")
    planner.add_argument("repo")
    planner.add_argument("bundle")
    planner.add_argument("--scope", choices=("min", "medium", "high"), default="medium")
    planner.add_argument("--session", required=True)
    planner.add_argument("--project")
    planner.add_argument("--into")
    finisher = subparsers.add_parser("finish")
    finisher.add_argument("repo")
    finisher.add_argument("job_id")
    finisher.add_argument("--session", required=True)
    finisher.add_argument("--project")
    finisher.add_argument("--status", choices=("completed", "cancelled"), required=True)
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(json.dumps(
            plan(args.repo, args.bundle, args.scope, args.session, args.into, args.project),
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ))
        return 0
    controller = JobController(
        args.project or os.environ.get("CLAUDE_PROJECT_DIR") or args.repo, args.session
    )
    success = (
        controller.accept_result(args.job_id, "context_capsule")
        if args.status == "completed"
        else controller.cancel(args.job_id)
    )
    print(json.dumps({"status": args.status if success else "ignored", "job_id": args.job_id}))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
