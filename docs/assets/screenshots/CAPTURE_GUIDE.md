# Screenshot capture guide

The README references five screenshots that live in this folder. Capture them
from the running app and save them with the exact file names below — then the
README gallery renders correctly.

## How to capture (macOS)

1. Open the app and resize the window to roughly its default size (about
   1280×860). A consistent window size keeps all shots aligned.
2. Press `Cmd + Shift + 4`, then press `Space`, then click the app window. macOS
   captures just the window (with a soft shadow) to your Desktop.
3. Rename the file to the target name below and move it into this folder
   (`docs/assets/screenshots/`).
4. Keep files reasonably small — PNG, under ~600 KB each. If a shot is large,
   downscale to ~1600 px wide.

Tip: use a realistic demo project (for example one with Terraform / GitLab CI /
Docker) so the screenshots show meaningful content, not an empty workspace.

## The five shots

| File name | Screen | What it should show |
|-----------|--------|---------------------|
| `01-ask.png` | **Ask** (hero, dark theme) | A real question with an answer grounded in the project, the sources list with match bars visible. This is the hero image. |
| `02-setup.png` | **Guided setup** | The full-window setup flow — ideally the "Give your project a local brain" step with the model checklist (Ollama running, models installed/downloading). |
| `03-overview.png` | **Project overview** | The workspace overview for a ready project (summary, detected tech, status). |
| `04-models.png` | **Models** | The Models screen — Choose & install, or the Compare view with two models side by side. |
| `05-light.png` | **Light theme** | Any main screen (Ask or Overview) in light theme, to show theme support. |

If you only have time for one, capture `01-ask.png` — it is the hero image and
the most important. The gallery degrades gracefully if some are missing.
