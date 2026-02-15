from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .utils import atomic_write_text, ensure_dir


DEFAULT_CONFIG: dict[str, Any] = {
    "taxonomy": {
        "core_categories": ["idea", "todo", "reference", "log"],
        "allow_custom_tags": True,
    },
    "summarization": {
        "enabled": True,
        "min_words": 180,
        "batch_trigger_count": 5,
        "redundancy_similarity_threshold": 0.85,
    },
    "git": {
        "default_branch": "main",
        "commit_prefix": "memo:",
    },
}


@dataclass
class TaxonomyConfig:
    core_categories: list[str]
    allow_custom_tags: bool


@dataclass
class SummarizationConfig:
    enabled: bool
    min_words: int
    batch_trigger_count: int
    redundancy_similarity_threshold: float


@dataclass
class GitConfig:
    default_branch: str
    commit_prefix: str


@dataclass
class AppConfig:
    taxonomy: TaxonomyConfig
    summarization: SummarizationConfig
    git: GitConfig

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    output = dict(base)
    for key, value in override.items():
        if key in output and isinstance(output[key], dict) and isinstance(value, dict):
            output[key] = _deep_merge(output[key], value)
        else:
            output[key] = value
    return output


def _load_yaml_or_json(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(content)
        return loaded or {}
    except ModuleNotFoundError:
        pass

    try:
        loaded_json = json.loads(content)
        if isinstance(loaded_json, dict):
            return loaded_json
        raise ValueError("Config root must be an object")
    except json.JSONDecodeError as exc:
        raise ValueError(
            "configs/memo.yaml must be JSON-compatible YAML unless PyYAML is installed."
        ) from exc


def load_config(root: Path) -> AppConfig:
    config_path = root / "configs" / "memo.yaml"
    merged = dict(DEFAULT_CONFIG)
    if config_path.exists():
        merged = _deep_merge(DEFAULT_CONFIG, _load_yaml_or_json(config_path))

    taxonomy_data = merged.get("taxonomy", {})
    summarization_data = merged.get("summarization", {})
    git_data = merged.get("git", {})

    return AppConfig(
        taxonomy=TaxonomyConfig(
            core_categories=list(taxonomy_data.get("core_categories", ["idea", "todo", "reference", "log"])),
            allow_custom_tags=bool(taxonomy_data.get("allow_custom_tags", True)),
        ),
        summarization=SummarizationConfig(
            enabled=bool(summarization_data.get("enabled", True)),
            min_words=int(summarization_data.get("min_words", 180)),
            batch_trigger_count=int(summarization_data.get("batch_trigger_count", 5)),
            redundancy_similarity_threshold=float(
                summarization_data.get("redundancy_similarity_threshold", 0.85)
            ),
        ),
        git=GitConfig(
            default_branch=str(git_data.get("default_branch", "main")),
            commit_prefix=str(git_data.get("commit_prefix", "memo:")),
        ),
    )


def init_default_config(root: Path) -> Path:
    config_path = root / "configs" / "memo.yaml"
    ensure_dir(config_path.parent)
    rendered = json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=True) + "\n"
    atomic_write_text(config_path, rendered)
    return config_path
