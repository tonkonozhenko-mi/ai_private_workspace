# Architecture

payments-api (ECS) -> SQS -> ledger-worker -> RDS Postgres (multi-AZ).
Terraform state lives in the acme-terraform-state S3 bucket with
DynamoDB locking. Deploys run from GitHub Actions on merge to main.
