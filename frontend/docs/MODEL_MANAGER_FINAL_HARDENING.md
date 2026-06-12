# Task 211 — Model manager final hardening

This task consolidates the local model manager into a calmer release-candidate screen.

## UX decisions

- Show a short model-manager summary first: installed models, downloads, and safety.
- Keep active downloads visible because they need user attention.
- Move download choices behind progressive disclosure.
- Move installed-model details behind progressive disclosure unless Ollama is offline.
- Move worker/safety details behind a quiet disclosure section.
- Avoid showing backend implementation details as the first thing the user sees.

## Safety decisions

- The frontend still never executes shell commands.
- Model downloads still run only through backend-owned jobs.
- Backend execution remains opt-in.
- Only allowlisted Ollama catalog models can be executed.
- Installing an embedding model does not rebuild the index automatically.
- Cancel remains safe-semantics first: queued jobs can be cancelled before running; running jobs are not killed aggressively from the UI.

## Visual decisions

- One summary grid at the top.
- Three focused sections: Download, Verify, Safety.
- Consistent spacing, radius, typography, and dark-theme treatment.
- Less noise by default, more detail only when opened.
