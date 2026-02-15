from __future__ import annotations

import unittest

from memo.config import SummarizationConfig
from memo.models import StageItem
from memo.summarize import build_summary, summarization_signals


class SummarizeTests(unittest.TestCase):
    def _item(self, body: str) -> StageItem:
        return StageItem(
            source_path="/tmp/n.md",
            source_rel_path="stage/inbox/n.md",
            content_hash="abc",
            created_at="2026-02-15T00:00:00+00:00",
            frontmatter={},
            body=body,
            content=body,
        )

    def test_long_entry_triggers_summary(self) -> None:
        config = SummarizationConfig(
            enabled=True,
            min_words=20,
            batch_trigger_count=5,
            redundancy_similarity_threshold=0.9,
        )
        item = self._item("word " * 25)
        signals, similarity = summarization_signals(item, pending_count=1, config=config, existing_summary_texts=[])
        self.assertIn("long_entry", signals)
        self.assertGreaterEqual(similarity, 0.0)

    def test_build_summary_extracts_actions_for_todo(self) -> None:
        body = "- [ ] write design doc\n- [ ] review roadmap\nThis note tracks tasks."
        item = self._item(body)
        summary = build_summary(item, category="todo", triggered_by=["batch_threshold"], redundancy_score=0.0)
        self.assertTrue(summary.short_summary)
        self.assertGreaterEqual(len(summary.actions), 1)


if __name__ == "__main__":
    unittest.main()
