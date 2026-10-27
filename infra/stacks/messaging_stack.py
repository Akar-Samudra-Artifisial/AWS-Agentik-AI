"""MessagingStack: SNS topic inbound WhatsApp dari End User Messaging Social."""

from typing import Any

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from constructs import Construct


class MessagingStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, prefix: str, **kwargs: Any
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.inbound_topic = sns.Topic(
            self, "inbound-whatsapp", topic_name=f"{prefix}-inbound-whatsapp"
        )
        # Event destination EUM Social mem-publish lewat service principal-nya;
        # dibatasi ke akun sendiri via aws:SourceAccount.
        self.inbound_topic.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowEndUserMessagingSocialPublish",
                principals=[iam.ServicePrincipal("social-messaging.amazonaws.com")],
                actions=["sns:Publish"],
                resources=[self.inbound_topic.topic_arn],
                conditions={"StringEquals": {"aws:SourceAccount": self.account}},
            )
        )
        CfnOutput(self, "inbound-topic-arn", value=self.inbound_topic.topic_arn)
