"""KnowledgeStack (placeholder).

Keputusan: Knowledge Base + vector store dibuat manual via console (fallback INF-008),
ID-nya disimpan ke SSM /resolveai/<env>/kb/id. Stack ini hanya mengekspos bucket kb-docs.
TODO: ganti dengan L1 CfnKnowledgeBase/CfnDataSource bila waktu cukup.
"""

from typing import Any

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_s3 as s3
from constructs import Construct


class KnowledgeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        kb_bucket: s3.IBucket,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        CfnOutput(self, "kb-docs-bucket-arn", value=kb_bucket.bucket_arn)
