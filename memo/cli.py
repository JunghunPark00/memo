from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .commit_flow import commit_proposal
from .config import init_default_config, load_config
from .proposal import build_proposal, load_latest_proposal, load_proposal, save_proposal
from .stage import list_pending_stage_files, stage_add
from .utils import ensure_dir, project_root, read_jsonl


def ensure_layout(root: Path) -> None:
    required_dirs = [
        root / "configs",
        root / "stage" / "inbox",
        root / "stage" / "processed",
        root / "vault" / "ideas",
        root / "vault" / "todos",
        root / "vault" / "references",
        root / "vault" / "logs",
        root / "vault" / "summaries",
        root / "vault" / "index",
        root / ".memo" / "proposals",
    ]
    for directory in required_dirs:
        ensure_dir(directory)


def cmd_config_init(root: Path) -> int:
    ensure_layout(root)
    config_path = init_default_config(root)
    print(f"Initialized config at {config_path}")
    return 0


def cmd_stage_add(root: Path, source_path: str) -> int:
    ensure_layout(root)
    staged = stage_add(root, Path(source_path).expanduser().resolve())
    print(f"Staged file: {staged.relative_to(root)}")
    return 0


def cmd_stage_list(root: Path) -> int:
    ensure_layout(root)
    pending = list_pending_stage_files(root)
    if not pending:
        print("No pending staged files.")
        return 0

    print(f"Pending staged files ({len(pending)}):")
    for path in pending:
        print(f"- {path.relative_to(root)}")
    return 0


def cmd_process(root: Path) -> int:
    ensure_layout(root)
    config = load_config(root)
    proposal = build_proposal(root, config)

    if proposal.stats.get("total_items", 0) == 0:
        print("No staged files found in stage/inbox.")
        return 0

    json_path, md_path = save_proposal(root, proposal)
    print(f"Proposal created: {proposal.proposal_id}")
    print(f"- JSON: {json_path.relative_to(root)}")
    print(f"- Report: {md_path.relative_to(root)}")
    print(f"- Commit preview: {proposal.commit_message_preview}")
    return 0


def _load_for_review(root: Path, proposal_id: str | None):
    if proposal_id:
        if proposal_id == "latest":
            return load_latest_proposal(root)
        return load_proposal(root, proposal_id)
    return load_latest_proposal(root)


def cmd_review(root: Path, proposal_id: str | None) -> int:
    ensure_layout(root)
    proposal = _load_for_review(root, proposal_id)

    print(f"Proposal: {proposal.proposal_id}")
    print(f"Created: {proposal.created_at}")
    print(json.dumps(proposal.stats, indent=2))
    print(f"Commit preview: {proposal.commit_message_preview}")
    print("")
    for item in proposal.items:
        print(f"- {item.entry_id}")
        print(f"  status={item.status} category={item.classification.category} confidence={item.classification.confidence}")
        print(f"  source={item.source_stage_path}")
        print(f"  target={item.target_entry_path}")
        if item.summary:
            print(f"  summary_trigger={','.join(item.summary.triggered_by)}")
        if item.invalid_reason:
            print(f"  invalid_reason={item.invalid_reason}")
        if item.warnings:
            print(f"  warnings={' | '.join(item.warnings)}")
    return 0


def cmd_commit(root: Path, proposal_id: str) -> int:
    ensure_layout(root)
    config = load_config(root)
    if proposal_id == "latest":
        proposal = load_latest_proposal(root)
        proposal_id = proposal.proposal_id

    result = commit_proposal(root, proposal_id, config)
    print(f"Committed proposal: {result.proposal_id}")
    print(f"Commit ref: {result.commit_ref}")
    print(
        "Summary: "
        f"committed={result.committed_entries}, "
        f"duplicates={result.skipped_duplicates}, "
        f"invalid={result.invalid_entries}"
    )
    print(f"Message: {result.message}")
    return 0


def cmd_status(root: Path) -> int:
    ensure_layout(root)

    pending = list_pending_stage_files(root)
    proposal_files = sorted((root / ".memo" / "proposals").glob("*.json"))
    commits = read_jsonl(root / "vault" / "index" / "commits.jsonl")

    print(f"Pending staged files: {len(pending)}")
    print(f"Saved proposals: {len(proposal_files)}")
    if proposal_files:
        print(f"Latest proposal: {proposal_files[-1].stem}")
    else:
        print("Latest proposal: -")

    if commits:
        last = commits[-1]
        commit_ref = last.get("commit_ref") or last.get("git_sha") or "-"
        print(f"Last committed proposal: {last.get('proposal_id', '-')}")
        print(f"Last commit ref: {commit_ref}")
    else:
        print("Last committed proposal: -")
        print("Last commit ref: -")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memo", description="Memo staging and commit workflow")
    parser.add_argument("--root", help="Project root (defaults to current directory)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("init", help="Initialize default config")

    stage_parser = subparsers.add_parser("stage", help="Manage staged notes")
    stage_sub = stage_parser.add_subparsers(dest="stage_command", required=True)
    stage_add_parser = stage_sub.add_parser("add", help="Add a file to stage/inbox")
    stage_add_parser.add_argument("path", help="Path to source file")
    stage_sub.add_parser("list", help="List pending staged files")

    subparsers.add_parser("process", help="Classify and prepare a proposal from stage/inbox")

    review_parser = subparsers.add_parser("review", help="Review proposal details")
    review_parser.add_argument("proposal_id", nargs="?", default="latest", help="Proposal ID or 'latest'")

    commit_parser = subparsers.add_parser("commit", help="Finalize approved proposal into vault and commit ledger")
    commit_parser.add_argument("proposal_id", help="Proposal ID or 'latest'")

    subparsers.add_parser("status", help="Show workflow status")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = project_root(args.root)

    try:
        if args.command == "config" and args.config_command == "init":
            return cmd_config_init(root)

        if args.command == "stage":
            if args.stage_command == "add":
                return cmd_stage_add(root, args.path)
            if args.stage_command == "list":
                return cmd_stage_list(root)

        if args.command == "process":
            return cmd_process(root)

        if args.command == "review":
            return cmd_review(root, args.proposal_id)

        if args.command == "commit":
            return cmd_commit(root, args.proposal_id)

        if args.command == "status":
            return cmd_status(root)

        parser.print_help()
        return 1

    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
