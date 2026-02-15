from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .classify import classify_item
from .config import AppConfig
from .models import Proposal, ProposalItem
from .stage import load_pending_stage_items, resolve_entry_id
from .storage import target_entry_relative_path, target_summary_relative_path
from .summarize import build_summary, load_existing_summary_texts, summarization_signals
from .utils import atomic_write_json, atomic_write_text, ensure_dir, now_utc_iso


def proposal_dir(root: Path) -> Path:
    return root / ".memo" / "proposals"


def _new_proposal_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"{ts}_{suffix}"


def build_proposal(root: Path, config: AppConfig) -> Proposal:
    stage_items = load_pending_stage_items(root)
    existing_summary_texts = load_existing_summary_texts(root)
    pending_count = len(stage_items)

    proposal_id = _new_proposal_id()
    items: list[ProposalItem] = []

    for stage_item in stage_items:
        entry_id = resolve_entry_id(stage_item)
        classification = classify_item(stage_item, config.taxonomy)

        status = "ready"
        invalid_reason = None
        warnings = list(stage_item.warnings)
        if not stage_item.body.strip():
            status = "invalid"
            invalid_reason = "empty body"

        signals, redundancy = summarization_signals(
            stage_item,
            pending_count=pending_count,
            config=config.summarization,
            existing_summary_texts=existing_summary_texts,
        )

        summary = None
        target_summary_path = None
        if status == "ready" and signals:
            summary = build_summary(
                item=stage_item,
                category=classification.category,
                triggered_by=signals,
                redundancy_score=redundancy,
            )
            target_summary_path = target_summary_relative_path(entry_id)

        target_entry_path = target_entry_relative_path(entry_id, category=classification.category)

        items.append(
            ProposalItem(
                entry_id=entry_id,
                source_stage_path=stage_item.source_rel_path,
                content_hash=stage_item.content_hash,
                created_at=stage_item.created_at,
                body=stage_item.body,
                frontmatter=stage_item.frontmatter,
                warnings=warnings,
                classification=classification,
                summary=summary,
                target_entry_path=target_entry_path,
                target_summary_path=target_summary_path,
                status=status,
                invalid_reason=invalid_reason,
            )
        )

    ready_count = len([item for item in items if item.status == "ready"])
    invalid_count = len([item for item in items if item.status == "invalid"])
    summary_count = len([item for item in items if item.summary is not None])

    commit_preview = f"{config.git.commit_prefix} apply proposal {proposal_id} ({ready_count} entries)"

    proposal = Proposal(
        proposal_id=proposal_id,
        created_at=now_utc_iso(),
        items=items,
        stats={
            "total_items": len(items),
            "ready_items": ready_count,
            "invalid_items": invalid_count,
            "summary_items": summary_count,
        },
        config_snapshot=config.to_dict(),
        commit_message_preview=commit_preview,
    )

    return proposal


def _render_proposal_markdown(proposal: Proposal) -> str:
    lines = [
        f"# Proposal {proposal.proposal_id}",
        "",
        f"Created: {proposal.created_at}",
        f"Total items: {proposal.stats.get('total_items', 0)}",
        f"Ready items: {proposal.stats.get('ready_items', 0)}",
        f"Invalid items: {proposal.stats.get('invalid_items', 0)}",
        f"Summary items: {proposal.stats.get('summary_items', 0)}",
        "",
        f"Commit preview: `{proposal.commit_message_preview}`",
        "",
        "## Items",
    ]

    for item in proposal.items:
        lines.extend(
            [
                "",
                f"### {item.entry_id}",
                f"- status: {item.status}",
                f"- source: `{item.source_stage_path}`",
                f"- category: `{item.classification.category}`",
                f"- confidence: {item.classification.confidence}",
                f"- tags: {', '.join(item.classification.tags)}",
                f"- target entry: `{item.target_entry_path}`",
                f"- target summary: `{item.target_summary_path or '-'}`",
            ]
        )
        if item.invalid_reason:
            lines.append(f"- invalid reason: {item.invalid_reason}")
        if item.warnings:
            lines.append(f"- warnings: {'; '.join(item.warnings)}")
        if item.summary:
            lines.append(f"- summary trigger: {', '.join(item.summary.triggered_by)}")

    lines.append("")
    return "\n".join(lines)


def save_proposal(root: Path, proposal: Proposal) -> tuple[Path, Path]:
    directory = proposal_dir(root)
    ensure_dir(directory)
    json_path = directory / f"{proposal.proposal_id}.json"
    md_path = directory / f"{proposal.proposal_id}.md"

    atomic_write_json(json_path, proposal.to_dict())
    atomic_write_text(md_path, _render_proposal_markdown(proposal))
    return json_path, md_path


def load_proposal(root: Path, proposal_id: str) -> Proposal:
    json_path = proposal_dir(root) / f"{proposal_id}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Proposal not found: {proposal_id}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return Proposal.from_dict(payload)


def latest_proposal_id(root: Path) -> str | None:
    directory = proposal_dir(root)
    if not directory.exists():
        return None
    candidates = sorted(directory.glob("*.json"))
    if not candidates:
        return None
    return candidates[-1].stem


def load_latest_proposal(root: Path) -> Proposal:
    latest = latest_proposal_id(root)
    if latest is None:
        raise FileNotFoundError("No proposals found")
    return load_proposal(root, latest)
