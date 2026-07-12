# acme-payments-platform

Payment processing platform for ACME Corp. Terraform-managed AWS
infrastructure, FastAPI services, GitHub Actions CI/CD.

## Environments
- dev, staging, prod (see terraform/environments)

## Services
- payments-api: REST API for payment intents
- ledger-worker: async double-entry bookkeeping

## Data
- db/migrations: customers, orders, order_events (Flyway-style, applied by number)

## Tests
- `make test` — pytest, in tests/

## Documents
- docs/runbook.docx: deploy, rollback, and what breaks at 3am
- finance/costs.csv: monthly cloud spend by environment
