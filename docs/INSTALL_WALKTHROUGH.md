# Install walkthrough (with screenshots)

From the download to your first answer — eight steps, every one of them on your
own Mac (no cloud, no accounts). The same flow applies on Windows with the
platform differences noted in the [README](../README.md#install-and-first-run).

<table>
  <tr>
    <td width="50%"><img src="assets/screenshots/step-1-install.png" alt="Drag the app into the Applications folder" width="100%"><br><sub><b>1 · Install</b> — open the downloaded <code>.dmg</code> and drag <b>AI Private Workspace</b> into <b>Applications</b>.</sub></td>
    <td width="50%"><img src="assets/screenshots/step-2-welcome.png" alt="Local-first welcome screen" width="100%"><br><sub><b>2 · Welcome</b> — launch it and click <b>Open a project folder</b>. Your files stay on your computer.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="assets/screenshots/step-3-create-workspace.png" alt="Create a local workspace and choose a role lens" width="100%"><br><sub><b>3 · Create a workspace</b> — name it, pick the folder, choose a role lens (DevOps, Developer, Tester, BA…) and whether the project is remembered.</sub></td>
    <td width="50%"><img src="assets/screenshots/step-4-scan.png" alt="Scan your project files locally" width="100%"><br><sub><b>4 · Scan</b> — a quick local pass lists your files so the AI knows what it can search. Nothing leaves the Mac.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="assets/screenshots/step-5-engine.png" alt="Choose a local engine and download models" width="100%"><br><sub><b>5 · Choose an engine</b> — built-in <b>llama.cpp</b> (nothing to install) or <b>Ollama</b>. Downloads two small local models (answer + search), then <b>Start engine</b>.</sub></td>
    <td width="50%"><img src="assets/screenshots/step-6-build-context.png" alt="Build local search context (RAG index)" width="100%"><br><sub><b>6 · Build context</b> — turn the scanned files into a searchable local index so answers come from your real project.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="assets/screenshots/step-7-folder-access.png" alt="macOS folder access permission prompt" width="100%"><br><sub><b>7 · Grant folder access</b> — macOS asks once before the app reads your folder. Click <b>Allow</b>.</sub></td>
    <td width="50%"><img src="assets/screenshots/step-8-ask.png" alt="Ask questions and get answers grounded in your project" width="100%"><br><sub><b>8 · Ask</b> — ask about your code, infra, CI/CD, or setup. Answers cite sources from your project and stay on your computer.</sub></td>
  </tr>
</table>

The app follows your system light/dark preference:

<p align="center">
  <img src="assets/screenshots/06-dark-ask.png" alt="Ask screen in dark theme" width="720">
</p>

## A few more screens

<table>
  <tr>
    <td width="50%"><img src="assets/screenshots/14-command-palette.png" alt="Command palette: jump to any repo, group, section or file" width="100%"><br><sub><b>Command palette</b> — <code>Cmd/Ctrl-K</code> to jump to any repository, group, section, or file.</sub></td>
    <td width="50%"><img src="assets/screenshots/13-security.png" alt="Security lens: scanners in CI and security-relevant findings" width="100%"><br><sub><b>Security lens</b> — which scan/audit steps run in CI, plus the security-relevant findings, each backed by a file.</sub></td>
  </tr>
</table>

> Screenshots are taken on a demo project and any project names, file paths, and
> contributor details are redacted. Capturing new ones? See
> [`assets/screenshots/CAPTURE_GUIDE.md`](assets/screenshots/CAPTURE_GUIDE.md).
