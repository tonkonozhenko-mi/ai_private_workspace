"""Pre-registered question sets for the external corpora.

Every ``expected_paths`` entry below was verified against the pinned commit's
file tree (GitHub trees API, 2026-07-13) BEFORE the first scored run. The rule
for editing this file: questions may be ADDED or RETIRED (with a commit message
saying why), never reworded to chase a better score — that is the whole value
of the benchmark.

Questions are phrased the way an engineer inheriting the project would ask,
not as keyword queries.
"""

from __future__ import annotations

from eval.golden_set import (
    CLASS_PROJECT_BROAD,
    CLASS_PROJECT_PRECISE,
    CLASS_SHOULD_ABSTAIN,
    QuestionCase,
)

# --- terraform-aws-vpc @ 3ffbd46 (v6.6.1) ---------------------------------

GOLDEN_SET_TF_VPC: tuple[QuestionCase, ...] = (
    QuestionCase(
        "vpc-pp-flow-logs",
        "How do I enable VPC flow logs, and where does their IAM role come from?",
        CLASS_PROJECT_PRECISE,
        ("vpc-flow-logs.tf", "modules/flow-log/main.tf"),
    ),
    QuestionCase(
        "vpc-pp-endpoints",
        "How do I create interface VPC endpoints with this module?",
        CLASS_PROJECT_PRECISE,
        ("modules/vpc-endpoints/main.tf",),
    ),
    QuestionCase(
        "vpc-pp-nat",
        "Where are NAT gateways created, and how does one-per-availability-zone work?",
        CLASS_PROJECT_PRECISE,
        ("main.tf",),
    ),
    QuestionCase(
        "vpc-pp-ipam",
        "Is there an example of allocating the VPC CIDR from IPAM?",
        CLASS_PROJECT_PRECISE,
        ("examples/ipam/main.tf",),
    ),
    QuestionCase(
        "vpc-pp-ipv6",
        "How do I configure an IPv6-only VPC?",
        CLASS_PROJECT_PRECISE,
        ("examples/ipv6-only/main.tf",),
    ),
    QuestionCase(
        "vpc-pp-nacl",
        "Where are custom network ACL rules demonstrated?",
        CLASS_PROJECT_PRECISE,
        ("examples/network-acls/main.tf",),
    ),
    QuestionCase(
        "vpc-pp-upgrade4",
        "What do I need to change when upgrading this module to version 4?",
        CLASS_PROJECT_PRECISE,
        ("docs/UPGRADE-4.0.md",),
    ),
    QuestionCase(
        "vpc-pp-wrappers",
        "How do I consume this module through Terragrunt wrappers?",
        CLASS_PROJECT_PRECISE,
        ("wrappers/README.md", "wrappers/main.tf"),
    ),
    QuestionCase(
        "vpc-pp-secondary-cidr",
        "How are secondary CIDR blocks attached to the VPC?",
        CLASS_PROJECT_PRECISE,
        ("examples/secondary-cidr-blocks/main.tf", "main.tf"),
    ),
    QuestionCase(
        "vpc-pb-what", "What is this repository and what does it provide?", CLASS_PROJECT_BROAD
    ),
    QuestionCase(
        "vpc-pb-examples", "What example configurations ship with this module?", CLASS_PROJECT_BROAD
    ),
    QuestionCase("vpc-sa-borscht", "What is a good recipe for borscht?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("vpc-sa-weather", "What's the weather like tomorrow?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("vpc-sa-hello", "Hi! How is your day going?", CLASS_SHOULD_ABSTAIN),
)


# --- GoogleCloudPlatform/microservices-demo @ 9a4616e ----------------------

GOLDEN_SET_BOUTIQUE: tuple[QuestionCase, ...] = (
    QuestionCase(
        "shop-pp-redis-cart",
        "How does the cart service store carts in Redis?",
        CLASS_PROJECT_PRECISE,
        ("src/cartservice/src/cartstore/RedisCartStore.cs",),
    ),
    QuestionCase(
        "shop-pp-grpc-api",
        "Where is the gRPC API shared by all the services defined?",
        CLASS_PROJECT_PRECISE,
        ("protos/demo.proto",),
    ),
    QuestionCase(
        "shop-pp-istio-gateway",
        "How is the frontend exposed through the Istio gateway?",
        CLASS_PROJECT_PRECISE,
        ("istio-manifests/frontend-gateway.yaml", "istio-manifests/frontend.yaml"),
    ),
    QuestionCase(
        "shop-pp-cart-deploy",
        "What resource limits and health probes does the cart service deployment set?",
        CLASS_PROJECT_PRECISE,
        ("kubernetes-manifests/cartservice.yaml",),
    ),
    QuestionCase(
        "shop-pp-checkout",
        "How does the checkout service orchestrate placing an order?",
        CLASS_PROJECT_PRECISE,
        ("src/checkoutservice/main.go",),
    ),
    QuestionCase(
        "shop-pp-single-manifest",
        "Can I deploy the whole demo from a single manifest, and where is it?",
        CLASS_PROJECT_PRECISE,
        ("release/kubernetes-manifests.yaml",),
    ),
    QuestionCase(
        "shop-pp-adservice",
        "How does the ad service decide which ads to serve?",
        CLASS_PROJECT_PRECISE,
        ("src/adservice/src/main/java/hipstershop/AdService.java",),
    ),
    QuestionCase(
        "shop-pp-dev-guide",
        "How do I run and develop this project locally?",
        CLASS_PROJECT_PRECISE,
        ("docs/development-guide.md",),
    ),
    QuestionCase(
        "shop-pp-helm",
        "Is there a Helm chart for this demo, and where is it documented?",
        CLASS_PROJECT_PRECISE,
        ("helm-chart/README.md",),
    ),
    QuestionCase("shop-pb-what", "What is this project about?", CLASS_PROJECT_BROAD),
    QuestionCase(
        "shop-pb-langs",
        "Which languages and frameworks are the services written in?",
        CLASS_PROJECT_BROAD,
    ),
    QuestionCase("shop-sa-poem", "Write me a short poem about autumn.", CLASS_SHOULD_ABSTAIN),
    QuestionCase("shop-sa-stock", "What is Google's stock price today?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("shop-sa-thanks", "Thanks, that's all for now!", CLASS_SHOULD_ABSTAIN),
)


# --- fastapi/full-stack-fastapi-template @ 7d80b85 --------------------------

GOLDEN_SET_FASTAPI_TMPL: tuple[QuestionCase, ...] = (
    QuestionCase(
        "fst-pp-login",
        "How does the login endpoint issue an access token?",
        CLASS_PROJECT_PRECISE,
        ("backend/app/api/routes/login.py", "backend/app/core/security.py"),
    ),
    QuestionCase(
        "fst-pp-hashing",
        "How are user passwords hashed and verified?",
        CLASS_PROJECT_PRECISE,
        ("backend/app/core/security.py",),
    ),
    QuestionCase(
        "fst-pp-models",
        "Where are the database models for users and items defined?",
        CLASS_PROJECT_PRECISE,
        ("backend/app/models.py",),
    ),
    QuestionCase(
        "fst-pp-migrations",
        "How are database schema migrations configured?",
        CLASS_PROJECT_PRECISE,
        ("backend/app/alembic/env.py",),
    ),
    QuestionCase(
        "fst-pp-settings",
        "Where do application settings and environment configuration live?",
        CLASS_PROJECT_PRECISE,
        ("backend/app/core/config.py",),
    ),
    QuestionCase(
        "fst-pp-reset-email",
        "How does the password-recovery email get generated and sent?",
        CLASS_PROJECT_PRECISE,
        ("backend/app/utils.py", "backend/app/api/routes/login.py"),
    ),
    QuestionCase(
        "fst-pp-compose",
        "What services does the local compose stack run?",
        CLASS_PROJECT_PRECISE,
        ("compose.yml",),
    ),
    QuestionCase(
        "fst-pp-backend-ci",
        "What does CI run against the backend on a pull request?",
        CLASS_PROJECT_PRECISE,
        (".github/workflows/test-backend.yml",),
    ),
    QuestionCase(
        "fst-pp-frontend-login",
        "Where is the frontend login page implemented?",
        CLASS_PROJECT_PRECISE,
        ("frontend/src/routes/login.tsx",),
    ),
    QuestionCase(
        "fst-pp-deploy",
        "How is this template deployed to a server?",
        CLASS_PROJECT_PRECISE,
        ("deployment.md",),
    ),
    QuestionCase("fst-pb-what", "What is this project about?", CLASS_PROJECT_BROAD),
    QuestionCase(
        "fst-pb-stack", "What is the technology stack, front to back?", CLASS_PROJECT_BROAD
    ),
    QuestionCase("fst-sa-movie", "Recommend me a good sci-fi movie.", CLASS_SHOULD_ABSTAIN),
    QuestionCase("fst-sa-time", "What time is it in Kyiv right now?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("fst-sa-js", "Is JavaScript better than Python in general?", CLASS_SHOULD_ABSTAIN),
)


def golden_set_tf_vpc() -> tuple[QuestionCase, ...]:
    return GOLDEN_SET_TF_VPC


def golden_set_boutique() -> tuple[QuestionCase, ...]:
    return GOLDEN_SET_BOUTIQUE


def golden_set_fastapi_tmpl() -> tuple[QuestionCase, ...]:
    return GOLDEN_SET_FASTAPI_TMPL
