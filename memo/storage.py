from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Proposal, ProposalItem
from .utils import atomic_write_text, ensure_dir, now_utc_iso


CATEGORY_FOLDER_MAP = {
    "idea": "ideas",
    "todo": "todos",
    "reference": "references",
    "log": "logs",
}


def category_folder(category: str) -> str:
    return CATEGORY_FOLDER_MAP.get(category, "references")


def target_entry_relative_path(entry_id: str, category: str) -> str:
    folder = category_folder(category)
    return str(Path("vault") / folder / f"{entry_id}.md")


def target_summary_relative_path(entry_id: str) -> str:
    return str(Path("vault") / "summaries" / f"{entry_id}.md")


def _render_frontmatter(payload: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in payload.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif value is None:
            lines.append(f"{key}: null")
        else:
            escaped = str(value).replace("\n", " ")
            lines.append(f"{key}: {escaped}")
    lines.append("---")
    return "\n".join(lines)


def render_entry_markdown(item: ProposalItem, proposal_id: str) -> str:
    summary_path = item.target_summary_path or ""
    frontmatter = {
        "entry_id": item.entry_id,
        "category": item.classification.category,
        "tags": item.classification.tags,
        "confidence": item.classification.confidence,
        "content_hash": item.content_hash,
        "source_stage_path": item.source_stage_path,
        "created_at": item.created_at,
        "proposal_id": proposal_id,
        "summary_path": summary_path,
    }
    fm = _render_frontmatter(frontmatter)
    body = item.body.strip()
    return fm + "\n\n" + body + "\n"


def render_summary_markdown(item: ProposalItem) -> str:
    assert item.summary is not None
    summary = item.summary

    lines = [
        f"# Summary for {item.entry_id}",
        "",
        summary.short_summary,
        "",
        "## Key Points",
    ]
    if summary.key_points:
        lines.extend(f"- {point}" for point in summary.key_points)
    else:
        lines.append("- (none)")

    lines.extend(["", "## Actions"])
    if summary.actions:
        lines.extend(f"- {action}" for action in summary.actions)
    else:
        lines.append("- (none)")

    lines.extend(["", "## Triggered By"])
    lines.extend(f"- {signal}" for signal in summary.triggered_by)
    lines.extend(["", f"Redundancy score: {summary.redundancy_score}", ""])
    return "\n".join(lines)


def apply_proposal_to_vault(
    root: Path,
    proposal: Proposal,
    existing_hashes: set[str],
) -> tuple[list[dict[str, Any]], list[str], int, int]:
    entry_records: list[dict[str, Any]] = []
    written_paths: list[str] = []
    committed_count = 0
    skipped_duplicates = 0

    for item in proposal.items:
        if item.status != "ready":
            continue

        if item.content_hash in existing_hashes:
            skipped_duplicates += 1
            continue

        entry_path = root / item.target_entry_path
        ensure_dir(entry_path.parent)
        atomic_write_text(entry_path, render_entry_markdown(item, proposal.proposal_id))
        written_paths.append(item.target_entry_path)

        summary_path = None
        if item.summary is not None and item.target_summary_path:
            summary_target = root / item.target_summary_path
            ensure_dir(summary_target.parent)
            atomic_write_text(summary_target, render_summary_markdown(item))
            written_paths.append(item.target_summary_path)
            summary_path = item.target_summary_path

        now = now_utc_iso()
        entry_records.append(
            {
                "entry_id": item.entry_id,
                "proposal_id": proposal.proposal_id,
                "content_hash": item.content_hash,
                "category": item.classification.category,
                "tags": item.classification.tags,
                "entry_path": item.target_entry_path,
                "summary_path": summary_path,
                "source_stage_path": item.source_stage_path,
                "created_at": item.created_at,
                "committed_at": now,
            }
        )
        existing_hashes.add(item.content_hash)
        committed_count += 1

    return entry_records, written_paths, committed_count, skipped_duplicates
