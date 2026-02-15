from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import StageItem
from .utils import ensure_dir, sha256_text


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def stage_inbox(root: Path) -> Path:
    return root / "stage" / "inbox"


def stage_processed(root: Path) -> Path:
    return root / "stage" / "processed"


def list_pending_stage_files(root: Path) -> list[Path]:
    inbox = stage_inbox(root)
    if not inbox.exists():
        return []
    return sorted(path for path in inbox.glob("**/*") if path.is_file())


def stage_add(root: Path, source_path: Path) -> Path:
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    inbox = stage_inbox(root)
    ensure_dir(inbox)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = source_path.name
    destination = inbox / f"{timestamp}_{base_name}"
    counter = 1
    while destination.exists():
        destination = inbox / f"{timestamp}_{counter}_{base_name}"
        counter += 1

    shutil.copy2(source_path, destination)
    return destination


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str, list[str]]:
    warnings: list[str] = []
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}, content, warnings

    fm_raw = match.group(1)
    body = content[match.end() :]

    frontmatter: dict[str, Any] = {}
    for line in fm_raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            warnings.append("frontmatter line ignored (missing ':'): " + stripped)
            continue
        key, value = stripped.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"')

    return frontmatter, body, warnings


def _to_iso_from_epoch(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).replace(microsecond=0).isoformat()


def load_stage_item(root: Path, path: Path) -> StageItem:
    raw_content = path.read_text(encoding="utf-8")
    frontmatter, body, warnings = _parse_frontmatter(raw_content)
    stripped_body = body.strip()
    if not stripped_body:
        warnings.append("body is empty")

    content_hash = sha256_text(raw_content)
    entry_id = str(uuid.uuid5(uuid.NAMESPACE_URL, content_hash))
    created_at = _to_iso_from_epoch(path.stat().st_mtime)

    return StageItem(
        source_path=str(path.resolve()),
        source_rel_path=str(path.relative_to(root)),
        content_hash=content_hash,
        created_at=created_at,
        frontmatter=frontmatter,
        body=stripped_body,
        warnings=warnings,
        content=raw_content,
    )


def load_pending_stage_items(root: Path) -> list[StageItem]:
    return [load_stage_item(root, path) for path in list_pending_stage_files(root)]


def resolve_entry_id(item: StageItem) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, item.content_hash))


def move_stage_to_processed(root: Path, source_rel_path: str, proposal_id: str) -> Path:
    src_path = root / source_rel_path
    if not src_path.exists():
        raise FileNotFoundError(f"Cannot move missing staged file: {src_path}")

    target_dir = stage_processed(root)
    ensure_dir(target_dir)
    target_name = f"{proposal_id}_{src_path.name}"
    destination = target_dir / target_name

    counter = 1
    while destination.exists():
        destination = target_dir / f"{proposal_id}_{counter}_{src_path.name}"
        counter += 1

    shutil.move(str(src_path), str(destination))
    return destination
