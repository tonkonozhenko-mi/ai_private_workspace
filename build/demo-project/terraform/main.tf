module "vpc" {
  source = "./modules/vpc"
  cidr   = var.vpc_cidr
}

module "payments_api" {
  source        = "./modules/ecs-service"
  name          = "payments-api"
  desired_count = var.api_replicas
  image         = "acme/payments-api:${var.release_tag}"
}

resource "aws_db_instance" "ledger" {
  engine         = "postgres"
  engine_version = "16.3"
  instance_class = "db.t4g.medium"
  multi_az       = true
}
