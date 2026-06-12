# Task 201 — Apple-grade calm UX pass

Goal: make the release-candidate interface feel calm, symmetric, readable, and human-first.

## What changed

- Startup/setup instructions inside the UI were reduced to a post-launch checklist.
- First-launch guidance now shows a simple numbered flow first.
- Readiness checks and developer commands are hidden behind disclosures.
- Large information blocks use one shared spacing rhythm.
- Buttons, inputs, cards, pills, and disclosures now share one control height and radius system.
- Conversation metadata chips were redesigned so they no longer look like disabled form fields.
- Dark theme surfaces were normalized to avoid washed-out gray blocks and inconsistent contrast.
- Technical/future roadmap panels stay visually quiet unless opened.

## UX rule going forward

The default screen should answer one question only: “What should I do next?”

Everything else should be either:

1. visible only after the user asks for it;
2. grouped in a small secondary card;
3. moved to documentation if it explains installation or developer setup.

## Safety remains unchanged

- The frontend does not run shell commands.
- The frontend does not pull models.
- The frontend does not start scans, indexing, rebuilds, MCP tools, or agent execution automatically.
- Dangerous capabilities remain explicit and approval-gated.
