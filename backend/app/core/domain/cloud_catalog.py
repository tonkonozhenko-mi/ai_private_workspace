"""Map a Terraform resource type to a (provider, service) pair.

Deterministic and offline. A curated table covers the common services with
friendly names; anything not in the table falls back to a sensible derivation
from the resource type's own tokens, so unknown resources are still grouped
under the right provider with a readable service name.
"""

_PROVIDER_PREFIXES = {
    "aws": "AWS",
    "google": "Google Cloud",
    "azurerm": "Azure",
    "azuread": "Azure AD",
    "kubernetes": "Kubernetes",
    "helm": "Helm",
    "cloudflare": "Cloudflare",
    "datadog": "Datadog",
    "github": "GitHub",
    "vault": "Vault",
    "digitalocean": "DigitalOcean",
}

# (provider_prefix, service_token) → friendly service. service_token is the
# second underscore-separated token of the resource type.
_SERVICE_NAMES = {
    ("aws", "s3"): "S3",
    ("aws", "lambda"): "Lambda",
    ("aws", "iam"): "IAM",
    ("aws", "dynamodb"): "DynamoDB",
    ("aws", "rds"): "RDS",
    ("aws", "db"): "RDS",
    ("aws", "ec2"): "EC2",
    ("aws", "instance"): "EC2",
    ("aws", "eks"): "EKS",
    ("aws", "ecs"): "ECS",
    ("aws", "ecr"): "ECR",
    ("aws", "sqs"): "SQS",
    ("aws", "sns"): "SNS",
    ("aws", "route53"): "Route 53",
    ("aws", "cloudfront"): "CloudFront",
    ("aws", "cloudwatch"): "CloudWatch",
    ("aws", "apigatewayv2"): "API Gateway",
    ("aws", "api"): "API Gateway",
    ("aws", "secretsmanager"): "Secrets Manager",
    ("aws", "kms"): "KMS",
    ("aws", "vpc"): "VPC",
    ("aws", "subnet"): "VPC",
    ("aws", "security"): "VPC",
    ("aws", "cloudwatch_event"): "EventBridge",
    ("aws", "cloudwatchevent"): "EventBridge",
    ("aws", "scheduler"): "EventBridge Scheduler",
    ("aws", "elasticache"): "ElastiCache",
    ("aws", "kinesis"): "Kinesis",
    ("aws", "glue"): "Glue",
    ("aws", "athena"): "Athena",
    ("aws", "sfn"): "Step Functions",
    ("aws", "elb"): "Load Balancing",
    ("aws", "lb"): "Load Balancing",
    ("aws", "acm"): "Certificate Manager",
    ("aws", "ssm"): "Systems Manager",
    ("aws", "efs"): "EFS",
    ("aws", "cognito"): "Cognito",
    ("google", "storage"): "Cloud Storage",
    ("google", "compute"): "Compute Engine",
    ("google", "container"): "GKE",
    ("google", "cloud"): "Cloud Run / Functions",
    ("google", "pubsub"): "Pub/Sub",
    ("google", "bigquery"): "BigQuery",
    ("google", "sql"): "Cloud SQL",
    ("azurerm", "storage"): "Storage",
    ("azurerm", "virtual"): "Virtual Machines / Network",
    ("azurerm", "kubernetes"): "AKS",
    ("azurerm", "app"): "App Service",
    ("azurerm", "function"): "Functions",
    ("azurerm", "cosmosdb"): "Cosmos DB",
    ("azurerm", "sql"): "SQL Database",
    ("azurerm", "key"): "Key Vault",
}

# EventBridge resources are named aws_cloudwatch_event_* — special-case the
# two-token service so it reads as EventBridge, not CloudWatch.
_SPECIAL_AWS = {
    "cloudwatch_event": "EventBridge",
    "cloudwatch_log": "CloudWatch Logs",
}


def cloud_for_resource(resource_type: str) -> tuple[str, str] | None:
    """Return (provider_label, service_label) for a Terraform resource type, or
    None if the provider prefix is unknown."""
    parts = resource_type.split("_")
    if len(parts) < 2:
        return None
    prefix = parts[0]
    provider = _PROVIDER_PREFIXES.get(prefix)
    if provider is None:
        return None

    if prefix == "aws":
        two = "_".join(parts[1:3]) if len(parts) >= 3 else ""
        if two in _SPECIAL_AWS:
            return provider, _SPECIAL_AWS[two]

    token = parts[1]
    service = _SERVICE_NAMES.get((prefix, token))
    if service is None:
        service = token.replace("-", " ").upper() if len(token) <= 3 else token.replace("-", " ").title()
    return provider, service
