## Summary

Describe the change and why it is needed.

## Validation

- [ ] `./scripts/audit_release_candidate.sh`
- [ ] backend targeted tests
- [ ] `cd frontend && npm ci && npm run build`

## Safety checklist

- [ ] No frontend shell execution added
- [ ] No automatic scan/index/rebuild/model download/MCP/Agent execution
- [ ] No runtime databases or build artifacts committed
