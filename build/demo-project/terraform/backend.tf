terraform {
  backend "s3" {
    bucket         = "acme-terraform-state"
    key            = "payments/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "acme-terraform-locks"
    encrypt        = true
  }
}
