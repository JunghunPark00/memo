from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memo.cli import ensure_layout
from memo.commit_flow import commit_proposal
from memo.config import init_default_config, load_config
from memo.proposal import build_proposal, save_proposal
from memo.stage import stage_add
from memo.utils import read_jsonl


class IntegrationFlowTests(unittest.TestCase):
    def test_stage_process_commit_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            ensure_layout(root)
            init_default_config(root)

            note = root / "note1.md"
            note.write_text("- [ ] Draft product memo\nNeed to ship by Friday.", encoding="utf-8")
            stage_add(root, note)

            proposal = build_proposal(root, load_config(root))
            save_proposal(root, proposal)

            result = commit_proposal(root, proposal.proposal_id, load_config(root))
            self.assertEqual(result.committed_entries, 1)
            self.assertTrue(result.commit_ref)

            entries = read_jsonl(root / "vault" / "index" / "entries.jsonl")
            self.assertEqual(len(entries), 1)
            commits = read_jsonl(root / "vault" / "index" / "commits.jsonl")
            self.assertEqual(len(commits), 1)
            self.assertEqual(commits[0]["commit_ref"], proposal.proposal_id)

            processed_files = list((root / "stage" / "processed").glob("*note1.md"))
            self.assertEqual(len(processed_files), 1)

    def test_duplicate_content_skips_second_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            ensure_layout(root)
            init_default_config(root)

            body = "Reference: https://example.com/docs\nHow-to notes"

            first = root / "first.md"
            first.write_text(body, encoding="utf-8")
            stage_add(root, first)
            p1 = build_proposal(root, load_config(root))
            save_proposal(root, p1)
            r1 = commit_proposal(root, p1.proposal_id, load_config(root))
            self.assertEqual(r1.committed_entries, 1)

            second = root / "second.md"
            second.write_text(body, encoding="utf-8")
            stage_add(root, second)
            p2 = build_proposal(root, load_config(root))
            save_proposal(root, p2)
            r2 = commit_proposal(root, p2.proposal_id, load_config(root))

            self.assertEqual(r2.committed_entries, 0)
            self.assertEqual(r2.skipped_duplicates, 1)


if __name__ == "__main__":
    unittest.main()
