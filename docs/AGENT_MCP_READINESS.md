# Task 213 — Agent + MCP readiness cleanup

This pass turns the Agent and MCP area into one calmer product story:

1. Describe the goal.
2. Preview a safe plan.
3. Review the MCP tools the plan may reference.
4. Approve and verify manually.

## UX changes

- Added a single Agent + MCP overview panel before the detailed Agent and MCP panels.
- Made the Agent panel focused on the primary action: creating a safe plan.
- Moved model capability details, guardrails, and recommended models into a disclosure section.
- Moved saved manual workflows into a disclosure section that opens only when workflows exist.
- Kept active previews and approval/readiness results visible because those are direct user outcomes.
- Added consistent Apple-like spacing and dark-mode card treatment for the Agent/MCP area.

## Safety position

- Frontend still never runs shell commands.
- MCP servers still do not start automatically.
- Agent workflows remain planning/manual tracking only.
- Approval gates record intent only.
- Future execution must be backend-side, sandboxed, allowlisted, and explicit.

## Product logic

MCP is not presented as something the user must understand first. The user starts with a goal and a plan. MCP remains the safe tool-visibility layer that can be inspected only when needed.
