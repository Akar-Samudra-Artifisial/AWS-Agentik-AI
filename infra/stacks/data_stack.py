"""DataStack: tabel DynamoDB (00-overview §10) dan bucket S3 privat."""

from typing import Any

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_s3 as s3
from constructs import Construct

_STR = ddb.AttributeType.STRING


class DataStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, prefix: str, **kwargs: Any
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.tables: dict[str, ddb.Table] = {}

        customers = self._table(prefix, "customers", "customer_id")
        customers.add_global_secondary_index(
            index_name="by_phone",
            partition_key=ddb.Attribute(name="phone_e164", type=_STR),
        )

        orders = self._table(prefix, "orders", "order_id")
        orders.add_global_secondary_index(
            index_name="by_customer",
            partition_key=ddb.Attribute(name="customer_id", type=_STR),
            sort_key=ddb.Attribute(name="created_at", type=_STR),
        )

        cases = self._table(prefix, "cases", "case_id")
        cases.add_global_secondary_index(
            index_name="by_customer",
            partition_key=ddb.Attribute(name="customer_id", type=_STR),
            sort_key=ddb.Attribute(name="updated_at", type=_STR),
        )
        cases.add_global_secondary_index(
            index_name="by_status",
            partition_key=ddb.Attribute(name="status", type=_STR),
            sort_key=ddb.Attribute(name="updated_at", type=_STR),
        )

        self._table(prefix, "messages", "case_id", sort_key="ts#msg_id")
        self._table(prefix, "agent_events", "case_id", sort_key="ts#seq")

        approvals = self._table(prefix, "approvals", "approval_id")
        approvals.add_global_secondary_index(
            index_name="by_status",
            partition_key=ddb.Attribute(name="status", type=_STR),
            sort_key=ddb.Attribute(name="requested_at", type=_STR),
        )

        self._table(prefix, "processed_events", "event_id", ttl_attribute="ttl")

        # Bucket `web` ada di WebStack: OAC menulis bucket policy yang mereferensikan
        # distribution, sehingga lintas-stack akan membentuk siklus dependensi.
        self.kb_bucket = self._bucket("kb-docs")

    def _table(
        self,
        prefix: str,
        name: str,
        partition_key: str,
        *,
        sort_key: str | None = None,
        ttl_attribute: str | None = None,
    ) -> ddb.Table:
        table = ddb.Table(
            self,
            f"{name}-table",
            table_name=f"{prefix}-{name}",
            partition_key=ddb.Attribute(name=partition_key, type=_STR),
            sort_key=ddb.Attribute(name=sort_key, type=_STR) if sort_key else None,
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute=ttl_attribute,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.tables[name] = table
        CfnOutput(self, f"{name}-table-name", value=table.table_name)
        return table

    def _bucket(self, name: str) -> s3.Bucket:
        # Nama bucket dibiarkan CDK-generated agar unik global.
        bucket = s3.Bucket(
            self,
            f"{name}-bucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        CfnOutput(self, f"{name}-bucket-name", value=bucket.bucket_name)
        return bucket
