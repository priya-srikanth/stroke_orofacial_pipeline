# Phase Kickoff Prompts

This directory contains phase kickoff and approval prompts prepared by Cowork
(the advisory agent) for Priya to paste into Claude Code (the execution agent).

## Workflow

1. Before each phase or sub-phase, Cowork writes a prompt file here.
2. Priya pastes a one-liner to Claude Code:
   > Read `docs/prompts/<filename>` and follow the instructions.
3. Claude Code reads the file and executes.

## Why files instead of direct paste

- Prompts can be long; single-line references are easier to paste than paragraphs.
- Prompts become a permanent git-tracked audit trail of what Claude Code was told.
- Reviewing a prompt as a file (e.g., in a PR diff) is cleaner than scrolling chat.

## Filename convention

- `phase-N-kickoff.md` — kicks off Phase N (enters plan mode, requires plan approval).
- `phase-N-approval.md` — approves an existing Phase N plan and authorizes execution.
- `phase-N.M-kickoff.md` — sub-phase prompts when a sub-phase needs a separate file (rare).
- Other one-off prompts (e.g., `review-foo.md`) named by scope.

## Convention for content

Each prompt file should include:

- **Context** — 1-2 sentences on what phase we're in.
- **Instructions** — numbered list of actions for Claude Code.
- **Constraints** — explicit data-safety reminders (reference `CLAUDE.md` sections).
- **Exit criteria** — what Claude Code should report when done, and whether to pause or proceed.

## Related files

- [`../DECISIONS.md`](../DECISIONS.md) — project-wide decisions log.
- [`../MIGRATION_LOG.md`](../MIGRATION_LOG.md) — per-phase implementation record.
- [`../DESIGN.md`](../DESIGN.md) — full design doc.
- [`../../CLAUDE.md`](../../CLAUDE.md) — project rules Claude Code auto-loads every session.
