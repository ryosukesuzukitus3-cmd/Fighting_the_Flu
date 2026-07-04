# Codex Memory

This directory stores project-local working memory for Codex sessions.

It is intentionally separate from `docs/` because these notes are not formal design documentation for players or maintainers. They are also separate from `AGENTS.md` because they are not hard rules.

## Priority

1. `AGENTS.md` is the source of mandatory workflow and repository rules.
2. Source code, tests, and stage JSON are the source of truth for implementation.
3. `.codex/memory/` is a lightweight handoff note for current direction, preferences, and recent decisions.

If memory conflicts with code, tests, `AGENTS.md`, or explicit user instructions, treat memory as stale and update or ignore it.

## Files

- `project.md`: durable project preferences, decision heuristics, and lessons learned.
- `roadmap.md`: current phase, next PRs, and known sequencing decisions.

The structure can change over time. If a split, merge, rename, or cleanup would make this memory more useful, Codex should propose the change before making it.

## Update Policy

- Add or update memory when a durable decision, repeated user preference, or multi-PR plan is established.
- Keep entries short and actionable.
- Do not store secrets, credentials, private external information, or one-off temporary facts.
- Prefer deleting or rewriting stale notes over accumulating contradictions.
- For structural changes to this directory, propose first. For small factual updates inside existing files, update when it is clearly useful.
