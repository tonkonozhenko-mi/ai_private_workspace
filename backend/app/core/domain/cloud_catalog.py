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
    ("aws", "ssoadmin"): "IAM Identity Center",
    ("aws", "sso"): "IAM Identity Center",
    ("aws", "identitystore"): "IAM Identity Center",
    ("aws", "service"): "Service Discovery",  # aws_service_discovery_*
    ("aws", "servicediscovery"): "Service Discovery",
    ("aws", "route"): "Route Tables",  # aws_route, aws_route_table (route53 is separate)
    ("aws", "customer"): "Customer Gateway",
    ("aws", "vpn"): "VPN",
    ("aws", "nat"): "NAT Gateway",
    ("aws", "wafv2"): "WAF",
    ("aws", "waf"): "WAF",
    ("aws", "wafregional"): "WAF",
    ("aws", "ses"): "SES",
    ("aws", "sesv2"): "SES",
    ("aws", "mskconnect"): "MSK Connect",
    ("aws", "msk"): "MSK",
    ("aws", "kafka"): "MSK",
    ("aws", "securitylake"): "Security Lake",
    ("aws", "guardduty"): "GuardDuty",
    ("aws", "securityhub"): "Security Hub",
    ("aws", "macie2"): "Macie",
    ("aws", "macie"): "Macie",
    ("aws", "inspector"): "Inspector",
    ("aws", "inspector2"): "Inspector",
    ("aws", "codeartifact"): "CodeArtifact",
    ("aws", "codebuild"): "CodeBuild",
    ("aws", "codepipeline"): "CodePipeline",
    ("aws", "codecommit"): "CodeCommit",
    ("aws", "codedeploy"): "CodeDeploy",
    ("aws", "datasync"): "DataSync",
    ("aws", "accessanalyzer"): "IAM Access Analyzer",
    ("aws", "transfer"): "Transfer Family",
    ("aws", "config"): "Config",
    ("aws", "budgets"): "Budgets",
    ("aws", "ce"): "Cost Explorer",
    ("aws", "organizations"): "Organizations",
    ("aws", "cloudtrail"): "CloudTrail",
    ("aws", "backup"): "Backup",
    ("aws", "autoscaling"): "Auto Scaling",
    ("aws", "appautoscaling"): "Auto Scaling",
    ("aws", "redshift"): "Redshift",
    ("aws", "emr"): "EMR",
    ("aws", "sagemaker"): "SageMaker",
    ("aws", "appsync"): "AppSync",
    ("aws", "amplify"): "Amplify",
    ("aws", "batch"): "Batch",
    ("aws", "fsx"): "FSx",
    ("aws", "globalaccelerator"): "Global Accelerator",
    ("aws", "apigateway"): "API Gateway",
    ("aws", "dms"): "DMS",
    ("aws", "eventbridge"): "EventBridge",
    ("aws", "pipes"): "EventBridge Pipes",
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
