# Brand assets

This folder is the **source of truth** for the app's logo and icons. The app
does not read these files at runtime — it uses copies placed in two locations
(see "How the app uses them" below). Keep the originals here so you, or anyone
forking the project, can swap in their own look by replacing files and re-copying.

## What's here

```
brand/
  logos/
    ai-private-workspace-logo-light.png   # full logo for light backgrounds
    ai-private-workspace-logo-dark.png    # full logo for dark backgrounds
  app-icons/
    light/  icon-{32,64,128,256,512,1024}.png   # app tile on a light background
    dark/   icon-{32,64,128,256,512,1024}.png   # app tile on a dark background
  tauri-icons/
    icon.png   icon.icns   icon.ico            # installed desktop app icon
    32x32.png  128x128.png  128x128@2x.png
```

## How the app uses them (two copy targets)

1. **In-app + browser tab icon** → `frontend/public/app-icon.png`
   Used as the sidebar brand mark and the browser/tab favicon. Currently a copy
   of `app-icons/light/icon-256x256.png`.

2. **Installed desktop app icon** → `frontend/src-tauri/icons/`
   Tauri builds the macOS/Windows app icon from these. Currently copies of
   everything in `tauri-icons/`.

## How to use your own logo and icons

1. Replace the files in this folder with your own, **keeping the same file names
   and sizes** (square PNGs for icons; `.icns` for macOS, `.ico` for Windows).
2. Re-copy them into the two targets:

   ```bash
   # from the repository root
   cp brand/app-icons/light/icon-256x256.png frontend/public/app-icon.png
   cp brand/tauri-icons/* frontend/src-tauri/icons/
   ```

3. Rebuild the desktop app so the installed icon updates.

That's it — no code changes are needed to swap the brand, only these file copies.

## Tips for a good app icon

- Keep it simple: an app icon must read clearly at 32px (tab, dock, taskbar).
  Fewer elements scale better than a detailed illustration.
- Provide both a light-background and dark-background version so the mark looks
  right in either theme.
- A square canvas with a small safe margin works best across platforms.
