## Summary

-

## Safety checklist

- [ ] Frontend does not execute shell commands.
- [ ] No automatic scan/index/rebuild/restart/model-download/MCP/Agent execution was added.
- [ ] Runtime data and build artifacts are not committed.
- [ ] Docs were updated when user-facing behavior changed.

## Validation

```bash
./scripts/audit_release_candidate.sh
cd backend && pytest -q tests/test_health.py tests/test_api_inventory.py
cd ../frontend && npm ci && npm run build
```
