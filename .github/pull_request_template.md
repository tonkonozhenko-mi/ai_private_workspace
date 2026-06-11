## Summary

-

## Safety impact

- [ ] Frontend does not execute shell commands.
- [ ] Scan/index/rebuild/model/MCP/agent actions remain explicit.
- [ ] Runtime/build data is not included.
- [ ] New backend behavior has tests or documented reason if not applicable.

## Validation

```bash
./scripts/audit_release_candidate.sh
cd backend && pytest -q
cd ../frontend && npm ci && npm run build
```

## Screenshots

Add screenshots for UI changes when helpful.
