"""CDK app ResolveAI. Urutan dependensi: Data -> Messaging -> Knowledge -> Web -> Compute."""

import os

import aws_cdk as cdk
from stacks.compute_stack import ComputeStack
from stacks.data_stack import DataStack
from stacks.knowledge_stack import KnowledgeStack
from stacks.messaging_stack import MessagingStack
from stacks.web_stack import WebStack

app = cdk.App()
env_name: str = app.node.try_get_context("env_name") or "dev"
prefix = f"resolveai-{env_name}"

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

data = DataStack(app, f"{prefix}-data", prefix=prefix, env=env)
messaging = MessagingStack(app, f"{prefix}-messaging", prefix=prefix, env=env)
KnowledgeStack(app, f"{prefix}-knowledge", kb_bucket=data.kb_bucket, env=env)
# Web dibuat sebelum Compute karena domain CloudFront dipakai untuk CORS API.
web = WebStack(app, f"{prefix}-web", prefix=prefix, env=env)
ComputeStack(
    app,
    f"{prefix}-compute",
    prefix=prefix,
    env_name=env_name,
    tables=data.tables,
    inbound_topic=messaging.inbound_topic,
    web_domain=web.distribution.distribution_domain_name,
    env=env,
)

cdk.Tags.of(app).add("project", "resolveai")
cdk.Tags.of(app).add("env", env_name)

app.synth()
