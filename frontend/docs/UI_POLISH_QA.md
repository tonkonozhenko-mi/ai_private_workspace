# UI Polish QA

Task 196 is a full visual consistency pass for the desktop-like frontend.

## Design intent

The UI should feel close to a native macOS utility:

- calm surfaces;
- readable typography;
- symmetric card spacing;
- predictable controls;
- no clipped dropdowns or long technical values;
- progressive disclosure instead of dense dashboard noise.

## Checked areas

- Sidebar workspace list
- Workspace header
- Tab navigation
- Overview metrics and dashboard cards
- Ask workspace flow
- Models dashboard
- Guided local model setup
- First launch checklist
- Reports
- Capabilities / safe agent planning
- Activity timeline
- Settings
- Light, dark, and system themes
- Compact density compatibility
- Small viewport behavior

## Safety note

This task is visual-only. It does not add frontend shell execution, automatic scan/index, model pull, rebuild, restart, MCP execution, or agent tool execution.
