# memo

`memo` is a local stage-to-vault note workflow:
1. Put raw notes in staging.
2. Process notes into a reviewable proposal (classification + optional summary).
3. Approve by committing proposal into the vault with a real git commit.

## Layout

- `stage/inbox/`: pending note files.
- `stage/processed/`: staged files moved after commit.
- `vault/{ideas,todos,references,logs}/`: canonical stored entries.
- `vault/summaries/`: generated summaries when heuristics trigger.
- `vault/index/entries.jsonl`: committed entry index.
- `vault/index/commits.jsonl`: runtime commit ledger (not git-tracked by default).
- `.memo/proposals/`: proposal JSON/Markdown artifacts.

## Install / Run

Use directly without install:

```bash
python -m memo.cli status
```

Or install editable:

```bash
pip install -e .
memo status
```

## Commands

```bash
memo config init
memo stage add path/to/note.md
memo stage list
memo process
memo review latest
memo commit latest
memo status
```

## Processing Rules

- Categories: `idea`, `todo`, `reference`, `log`.
- Summaries are generated only when heuristic signals trigger:
  - note is long (`min_words`),
  - staged batch size crosses threshold,
  - or high redundancy vs existing summaries.
- `memo commit` does not process unreviewed data directly; it applies an existing proposal.

## Git Requirements

Initialize git before committing proposals:

```bash
git init -b main
```

`memo commit` writes vault files and creates one git commit per proposal.
