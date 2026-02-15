from __future__ import annotations

import unittest

from memo.classify import classify_item
from memo.config import TaxonomyConfig
from memo.models import StageItem


class ClassifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.taxonomy = TaxonomyConfig(core_categories=["idea", "todo", "reference", "log"], allow_custom_tags=True)

    def test_todo_detection_from_checkboxes(self) -> None:
        item = StageItem(
            source_path="/tmp/n.md",
            source_rel_path="stage/inbox/n.md",
            content_hash="abc",
            created_at="2026-02-15T00:00:00+00:00",
            frontmatter={},
            body="- [ ] Write tests\n- [ ] Ship release",
            content="- [ ] Write tests\n- [ ] Ship release #release",
        )
        result = classify_item(item, self.taxonomy)
        self.assertEqual(result.category, "todo")
        self.assertIn("release", result.tags)

    def test_reference_default_when_ambiguous(self) -> None:
        item = StageItem(
            source_path="/tmp/n.md",
            source_rel_path="stage/inbox/n.md",
            content_hash="abc",
            created_at="2026-02-15T00:00:00+00:00",
            frontmatter={},
            body="Short note",
            content="Short note",
        )
        result = classify_item(item, self.taxonomy)
        self.assertEqual(result.category, "reference")


if __name__ == "__main__":
    unittest.main()
