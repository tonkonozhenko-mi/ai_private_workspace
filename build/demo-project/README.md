# acme-payments-platform

Payment processing platform for ACME Corp. Terraform-managed AWS
infrastructure, FastAPI services, GitHub Actions CI/CD.

## Environments
- dev, staging, prod (see terraform/environments)

## Services
- payments-api: REST API for payment intents
- ledger-worker: async double-entry bookkeeping
