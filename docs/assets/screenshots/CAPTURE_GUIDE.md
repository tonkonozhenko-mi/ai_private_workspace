# Screenshot capture guide

The README embeds the screenshots in this folder. Capture them from the running
app and save them with the **exact file names** below — then the README renders
correctly. Re-shoot whenever the icon, tabs, or layout change.

## How to capture (macOS)

1. Open the app and resize the window to roughly its default size (about
   **1280×860**). A consistent window size keeps every shot aligned.
2. Press `Cmd + Shift + 4`, then `Space`, then click the app window. macOS
   captures just the window (with a soft shadow) to your Desktop.
3. Rename the file to the target name and move it into this folder
   (`docs/assets/screenshots/`).
4. Keep files small — PNG, ideally under ~600 KB. If a shot is large, downscale
   to ~1600 px wide.

Tip: use a realistic demo project (Terraform / GitHub Actions / Docker, with some
git history) so the screenshots show meaningful content — and make sure the new
**pigeon** app icon is visible wherever the brand mark appears.

## Required — referenced directly by the README

| File name | Screen | What it should show |
|-----------|--------|---------------------|
| `01-ask.png` | **Ask** (hero, dark theme) | A real question with an answer grounded in the project, sources list with match bars. This is the hero image — the most important one. |
| `06-dark-ask.png` | **Ask** (dark theme) | Any Ask view in dark theme (can differ from the hero) to show theme support. |
| `step-1-install.png` | **Install** | The `.dmg` with the app being dragged into Applications (shows the **pigeon icon**). |
| `step-2-welcome.png` | **Welcome** | The local-first welcome screen (pigeon brand mark visible). |
| `step-3-create-workspace.png` | **Create a workspace** | The create form — name, folder, role lens (DevOps / Developer / Tester / BA), remember toggle. |
| `step-4-scan.png` | **Scan** | The local file scan / selection step. |
| `step-5-engine.png` | **Choose an engine** | Engine choice (llama.cpp / Ollama) with the model checklist. |
| `step-6-build-context.png` | **Build context** | Building the local search index. |
| `step-7-folder-access.png` | **Folder access** | The macOS folder-access permission prompt. |
| `step-8-ask.png` | **Ask** | First answer with sources — the payoff shot. |

## Recommended — show the newer capabilities

These aren't embedded yet; capture them and tell me, and I'll add a short
"Highlights" gallery to the README.

| File name | Screen | What it should show |
|-----------|--------|---------------------|
| `10-intelligence-map.png` | **Intelligence → Map** | The interactive project map; ideally a node selected so the blast-radius panel (depends on / affects) is visible. |
| `11-intelligence-tabs.png` | **Intelligence** | The sub-tab row showing the current tabs — Overview, Infrastructure, Deployment, Environments, Risks, Cloud, References, **Security**, Map — on a real infra repo. |
| `12-security.png` | **Intelligence → Security** | The security lens: scanners detected in CI + security-relevant findings. |
| `13-project-activity.png` | **Home → Project activity** | The git activity card expanded: momentum, who knows the code, how they ship, hotspots, "Changes together" (coupling). |
| `14-file-inspector.png` | **File inspector** | The file drawer open (owner, changes-together, connected-in-map, risks). Open it by clicking a file in "Where to start" or a hotspot. |
| `15-command-palette.png` | **Command palette** | `Cmd/Ctrl-K` open with a query and a few results across repos / sections / files. |
| `16-group.png` | **Project group** | A group's Intelligence: the repo filter chips + the environment matrix + technologies (shared vs unique). |

## Brand / social preview

The repository social preview already uses the pigeon brand
(`assets/brand/social-preview-1280x640.png`). To publish it:
**GitHub → repo → Settings → General → Social preview → Edit → upload that PNG.**
Re-upload only if the brand art changes.

If you only have time for one screenshot, capture `01-ask.png` — the gallery
degrades gracefully when others are missing.
