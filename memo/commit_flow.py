from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .config import AppConfig
from .models import CommitResult
from .proposal import load_proposal
from .stage import move_stage_to_processed
from .storage import apply_proposal_to_vault
from .utils import append_jsonl_atomic, ensure_dir, now_utc_iso, read_jsonl


def _restore_file(path: Path, previous_content: str | None) -> None:
    if previous_content is None:
        if path.exists():
            path.unlink()
    else:
        ensure_dir(path.parent)
        path.write_text(previous_content, encoding="utf-8")


def commit_proposal(root: Path, proposal_id: str, config: AppConfig) -> CommitResult:
    proposal = load_proposal(root, proposal_id)

    entries_index = root / "vault" / "index" / "entries.jsonl"
    commits_index = root / "vault" / "index" / "commits.jsonl"
    ensure_dir(entries_index.parent)

    commit_records = read_jsonl(commits_index)
    if any(record.get("proposal_id") == proposal_id for record in commit_records):
        raise RuntimeError(f"Proposal {proposal_id} was already committed")

    existing_entry_records = read_jsonl(entries_index)
    existing_hashes = {str(row.get("content_hash", "")) for row in existing_entry_records if row.get("content_hash")}

    previous_entries_index: str | None = None
    if entries_index.exists():
        previous_entries_index = entries_index.read_text(encoding="utf-8")

    previous_commits_index: str | None = None
    if commits_index.exists():
        previous_commits_index = commits_index.read_text(encoding="utf-8")

    moved_stage_files: list[tuple[Path, Path]] = []
    written_paths: list[str] = []

    invalid_entries = len([item for item in proposal.items if item.status == "invalid"])

    try:
        entry_records, written_paths, committed_entries, skipped_duplicates = apply_proposal_to_vault(
            root,
            proposal,
            existing_hashes=existing_hashes,
        )

        if entry_records:
            append_jsonl_atomic(entries_index, entry_records)
            if "vault/index/entries.jsonl" not in written_paths:
                written_paths.append("vault/index/entries.jsonl")

        for item in proposal.items:
            if item.status != "ready":
                continue
            source = root / item.source_stage_path
            destination = move_stage_to_processed(root, item.source_stage_path, proposal_id)
            moved_stage_files.append((destination, source))

        commit_message = (
            f"{config.git.commit_prefix} apply proposal {proposal.proposal_id} "
            f"({committed_entries} entries, {skipped_duplicates} duplicates, {invalid_entries} invalid)"
        )
        commit_ref = proposal.proposal_id

        commit_record: dict[str, Any] = {
            "proposal_id": proposal.proposal_id,
            "created_at": now_utc_iso(),
            "commit_ref": commit_ref,
            "committed_entries": committed_entries,
            "skipped_duplicates": skipped_duplicates,
            "invalid_entries": invalid_entries,
        }
        append_jsonl_atomic(commits_index, [commit_record])

        return CommitResult(
            proposal_id=proposal.proposal_id,
            commit_ref=commit_ref,
            committed_entries=committed_entries,
            skipped_duplicates=skipped_duplicates,
            invalid_entries=invalid_entries,
            message=commit_message,
        )

    except Exception:
        for rel_path in written_paths:
            path = root / rel_path
            if path.exists() and path.is_file():
                path.unlink()

        _restore_file(entries_index, previous_entries_index)
        _restore_file(commits_index, previous_commits_index)

        for moved_destination, original_source in reversed(moved_stage_files):
            if moved_destination.exists():
                ensure_dir(original_source.parent)
                shutil.move(str(moved_destination), str(original_source))

        raise
