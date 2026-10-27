"""WebStack: CloudFront + S3 (OAC) untuk static export dashboard."""

from typing import Any

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from constructs import Construct


class WebStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        prefix: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        web_bucket = s3.Bucket(
            self,
            "web-bucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        self.web_bucket = web_bucket

        # Static export (trailingSlash) menulis `cases/index.html` dst.; origin S3 REST
        # tidak punya default index di subfolder, jadi URI ditulis ulang di edge.
        index_rewrite = cloudfront.Function(
            self,
            "web-index-rewrite",
            runtime=cloudfront.FunctionRuntime.JS_2_0,
            code=cloudfront.FunctionCode.from_inline(
                "function handler(event) {\n"
                "  var request = event.request;\n"
                "  var uri = request.uri;\n"
                "  if (uri.endsWith('/')) {\n"
                "    request.uri = uri + 'index.html';\n"
                "  } else if (!uri.split('/').pop().includes('.')) {\n"
                "    request.uri = uri + '/index.html';\n"
                "  }\n"
                "  return request;\n"
                "}\n"
            ),
        )

        self.distribution = cloudfront.Distribution(
            self,
            "web-distribution",
            comment=f"{prefix}-web",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(web_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=index_rewrite,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            # Objek tak ada → S3 (OAC, tanpa ListBucket) membalas 403; tampilkan 404.html
            # dengan status 404 alih-alih menyamarkannya sebagai Overview.
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=status,
                    response_http_status=404,
                    response_page_path="/404.html",
                    ttl=Duration.seconds(0),
                )
                for status in (403, 404)
            ],
        )
        CfnOutput(self, "web-bucket-name", value=web_bucket.bucket_name)
        CfnOutput(self, "web-distribution-id", value=self.distribution.distribution_id)
        CfnOutput(
            self,
            "web-url",
            value=f"https://{self.distribution.distribution_domain_name}",
        )
