# Claude Code Context — Personal Budget Platform

Claude Code must follow the repository-wide agent rules in `AGENTS.md`.

Before making changes, read:

1. `AGENTS.md`
2. `.hermes/workflows/multi-agent-development.md`
3. Any task-specific plan under `.hermes/plans/`

Key reminders:

- Keep changes small and scoped.
- Use TDD for behavior changes.
- Do not commit secrets or generated junk.
- Do not run destructive commands without explicit human approval.
- For schema changes, include and verify Alembic upgrade/downgrade.
- For frontend work, use React + TypeScript + Vite under `frontend/` unless the plan says otherwise.

Use the handoff format from `AGENTS.md` when finishing a task.
