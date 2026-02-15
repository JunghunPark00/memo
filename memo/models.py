from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ClassificationResult:
    category: str
    tags: list[str]
    confidence: float
    reasoning: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassificationResult":
        return cls(
            category=data["category"],
            tags=list(data.get("tags", [])),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=str(data.get("reasoning", "")),
        )


@dataclass
class SummaryResult:
    short_summary: str
    key_points: list[str]
    actions: list[str]
    triggered_by: list[str]
    redundancy_score: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SummaryResult":
        redundancy = data.get("redundancy_score")
        return cls(
            short_summary=str(data.get("short_summary", "")),
            key_points=list(data.get("key_points", [])),
            actions=list(data.get("actions", [])),
            triggered_by=list(data.get("triggered_by", [])),
            redundancy_score=None if redundancy is None else float(redundancy),
        )


@dataclass
class ProposalItem:
    entry_id: str
    source_stage_path: str
    content_hash: str
    created_at: str
    body: str
    frontmatter: dict[str, Any]
    warnings: list[str]
    classification: ClassificationResult
    summary: SummaryResult | None
    target_entry_path: str
    target_summary_path: str | None
    status: str
    invalid_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProposalItem":
        return cls(
            entry_id=str(data["entry_id"]),
            source_stage_path=str(data["source_stage_path"]),
            content_hash=str(data["content_hash"]),
            created_at=str(data["created_at"]),
            body=str(data.get("body", "")),
            frontmatter=dict(data.get("frontmatter", {})),
            warnings=list(data.get("warnings", [])),
            classification=ClassificationResult.from_dict(dict(data.get("classification", {}))),
            summary=None
            if data.get("summary") is None
            else SummaryResult.from_dict(dict(data["summary"])),
            target_entry_path=str(data["target_entry_path"]),
            target_summary_path=data.get("target_summary_path"),
            status=str(data.get("status", "ready")),
            invalid_reason=data.get("invalid_reason"),
        )


@dataclass
class Proposal:
    proposal_id: str
    created_at: str
    items: list[ProposalItem]
    stats: dict[str, Any]
    config_snapshot: dict[str, Any]
    commit_message_preview: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "created_at": self.created_at,
            "items": [item.to_dict() for item in self.items],
            "stats": self.stats,
            "config_snapshot": self.config_snapshot,
            "commit_message_preview": self.commit_message_preview,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Proposal":
        return cls(
            proposal_id=str(data["proposal_id"]),
            created_at=str(data["created_at"]),
            items=[ProposalItem.from_dict(item) for item in data.get("items", [])],
            stats=dict(data.get("stats", {})),
            config_snapshot=dict(data.get("config_snapshot", {})),
            commit_message_preview=str(data.get("commit_message_preview", "")),
        )


@dataclass
class StageItem:
    source_path: str
    source_rel_path: str
    content_hash: str
    created_at: str
    frontmatter: dict[str, Any]
    body: str
    warnings: list[str] = field(default_factory=list)
    content: str = ""


@dataclass
class CommitResult:
    proposal_id: str
    git_sha: str
    committed_entries: int
    skipped_duplicates: int
    invalid_entries: int
    message: str
