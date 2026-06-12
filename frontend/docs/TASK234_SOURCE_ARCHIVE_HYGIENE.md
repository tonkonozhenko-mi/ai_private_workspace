# Task 234 — Source archive hygiene hardening

This task tightens the final v0.1 source release handoff checks.

## What changed

- The release audit now explicitly warns when local Python virtual environments are present under `backend/.venv`.
- The release audit now explicitly checks for TypeScript incremental build metadata (`*.tsbuildinfo`).
- Existing source archive generation already excludes these files; the audit now makes the local hygiene state visible before publication.

## Why it matters

The v0.1 source release is meant to be GitHub-ready source code, not a local developer workspace snapshot. Virtual environments and incremental build metadata are machine-specific artifacts and should not be committed or included in handoff archives.

## Safety

No runtime behavior changed. Frontend still does not execute shell commands, model downloads remain backend-owned and opt-in, and desktop packaging still follows the supervisor contract.
