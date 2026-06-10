# Release candidate UI review — Task 200

Goal: make the product feel calm, desktop-native, and understandable for a first-time user.

## What changed

- The Overview guided path now has one clear primary action instead of duplicated scan/index buttons.
- Advanced file-rule previews are hidden behind a disclosure so the main setup flow stays readable.
- The Models tab starts with the practical model state, while desktop packaging roadmap details are collapsed.
- Startup wording was corrected: launch instructions belong in external docs/package flow; in-app guidance only explains what to do after the app is open.
- Copy-only / safety language remains visible, but shorter and less alarming.
- Card radius, button sizing, spacing, and disclosure styling were aligned toward a softer macOS-like visual rhythm.

## UX rules for future changes

1. One primary action per visible section.
2. Advanced diagnostics go behind `details` or into Settings/Activity.
3. Do not explain how to start the app only inside the already-started UI.
4. Prefer human labels: “Build search context” instead of internal terms where possible.
5. Keep risky actions explicit, user-clicked, and never hidden behind page load.
6. Use empty states and next-step guidance instead of dense dashboards.

## Still intentionally not done

- No automatic model download from the frontend.
- No MCP execution from the frontend.
- No real double-click packaged app yet; this belongs to the next packaging milestone.
