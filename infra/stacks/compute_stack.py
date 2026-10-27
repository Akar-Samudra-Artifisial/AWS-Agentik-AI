"""ComputeStack: Lambda dispatcher (SNS) dan api (HTTP API Gateway)."""

from pathlib import Path
from typing import Any

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_lambda_event_sources as event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from constructs import Construct

INFRA_DIR = Path(__file__).resolve().parent.parent
PLACEHOLDER_DIR = INFRA_DIR / "placeholder_lambda"

# Tabel yang diakses tiap fungsi (least privilege).
DISPATCHER_TABLES = (
    "customers",
    "orders",
    "cases",
    "messages",
    "agent_events",
    "approvals",
    "processed_events",
)
API_TABLES = ("customers", "orders", "cases", "messages", "agent_events", "approvals")


class ComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        prefix: str,
        env_name: str,
        tables: dict[str, ddb.Table],
        inbound_topic: sns.ITopic,
        web_domain: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        ssm_prefix = f"/resolveai/{env_name}"
        table_env = {
            f"TABLE_{name.upper()}": t.table_name for name, t in tables.items()
        }
        # Identitas pengirim dibaca adapter messaging dari env; isi lewat
        # `cdk deploy -c ses_from_email=... -c sms_origination_identity=...`.
        messaging_env = {
            env_key: str(value)
            for env_key, ctx_key in (
                ("SES_FROM_EMAIL", "ses_from_email"),
                ("SMS_ORIGINATION_IDENTITY", "sms_origination_identity"),
                ("WA_PHONE_NUMBER_ID", "wa_phone_number_id"),
                ("WA_META_API_VERSION", "wa_meta_api_version"),
            )
            if (value := self.node.try_get_context(ctx_key))
        }
        common_env = {
            "ENV_NAME": env_name,
            "SSM_PREFIX": ssm_prefix,
            **table_env,
            **messaging_env,
        }
        ssm_read = iam.PolicyStatement(
            actions=[
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath",
            ],
            resources=[
                f"arn:{self.partition}:ssm:{self.region}:{self.account}:parameter{ssm_prefix}/*"
            ],
        )

        dispatcher = self._function(
            prefix, "dispatcher", memory=512, timeout=180, environment=common_env
        )
        dispatcher.add_event_source(event_sources.SnsEventSource(inbound_topic))
        dispatcher.add_to_role_policy(ssm_read)
        for name in DISPATCHER_TABLES:
            tables[name].grant_read_write_data(dispatcher)
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                # TODO: persempit ke ARN runtime setelah agentcore launch (SSM agent/runtime_arn).
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[
                    f"arn:{self.partition}:bedrock-agentcore:{self.region}:{self.account}:runtime/*"
                ],
            )
        )
        # Pesan keluar dari dispatcher (balasan sistem/eskalasi); penerima diturunkan dari kasus.
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ses:SendEmail",
                    "social-messaging:SendWhatsAppMessage",
                    "sms-voice:SendTextMessage",
                ],
                # TODO: persempit ke identity SES / phone-number-id setelah diketahui.
                resources=["*"],
            )
        )

        api = self._function(
            prefix,
            "api",
            memory=512,
            timeout=25,
            environment={
                **common_env,
                "DISPATCHER_FUNCTION_NAME": dispatcher.function_name,
                "DEMO_RESET_ENABLED": str(
                    self.node.try_get_context("demo_reset_enabled") or "false"
                ).lower(),
            },
        )
        api.add_to_role_policy(ssm_read)
        for name in API_TABLES:
            tables[name].grant_read_write_data(api)
        dispatcher.grant_invoke(api)

        http_api = apigw.HttpApi(
            self,
            "http-api",
            api_name=f"{prefix}-api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=[
                    self.node.try_get_context("dev_cors_origin")
                    or "http://localhost:3000",
                    f"https://{web_domain}",
                ],
                allow_methods=[apigw.CorsHttpMethod.ANY],
                allow_headers=["content-type", "authorization", "x-api-key"],
                max_age=Duration.hours(1),
            ),
            default_integration=integrations.HttpLambdaIntegration(
                "api-integration", api
            ),
        )
        CfnOutput(self, "api-url", value=http_api.api_endpoint)
        CfnOutput(self, "dispatcher-function-name", value=dispatcher.function_name)

    def _function(
        self,
        prefix: str,
        name: str,
        *,
        memory: int,
        timeout: int,
        environment: dict[str, str],
    ) -> _lambda.Function:
        log_group = logs.LogGroup(
            self,
            f"{name}-logs",
            log_group_name=f"/aws/lambda/{prefix}-{name}",
            retention=logs.RetentionDays.TWO_WEEKS,
        )
        code_path, handler = self._code(name)
        return _lambda.Function(
            self,
            f"{name}-fn",
            function_name=f"{prefix}-{name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler=handler,
            code=_lambda.Code.from_asset(str(code_path)),
            memory_size=memory,
            timeout=Duration.seconds(timeout),
            environment=environment,
            log_group=log_group,
        )

    def _code(self, name: str) -> tuple[Path, str]:
        """Asset + handler Lambda.

        Kode backend memakai import paket (`services`, `resolveai_common`, relative import),
        jadi asset harus berupa bundle (isi backend/ + packages/common + dependency) di
        context `lambda_bundle_path`. Selama bundle belum dibangun, pakai placeholder.
        """
        bundle = (
            INFRA_DIR / (self.node.try_get_context("lambda_bundle_path") or "")
        ).resolve()
        if (bundle / name / "handler.py").is_file():
            return bundle, f"{name}.handler.handler"
        return PLACEHOLDER_DIR, "handler.handler"
