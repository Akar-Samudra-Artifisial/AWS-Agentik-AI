"""AgentCore client (BE-008) against a botocore Stubber; no network."""

from __future__ import annotations

import io
import json

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from services.agent_client import (
    AgentCoreClient,
    AgentInvocationError,
    session_id_for_case,
)

pytestmark = pytest.mark.usefixtures("aws_env")

ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/resolveai-test"


def _streaming(data: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(data), len(data))


def test_invoke_sends_payload_and_decodes_json() -> None:
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    payload = {"event_type": "customer_message", "case_id": "CASE-20261027-0001"}
    session_id = session_id_for_case("CASE-20261027-0001")
    result = {"case_id": "CASE-20261027-0001", "case_status": "resolved", "actions": []}

    with Stubber(client) as stub:
        stub.add_response(
            "invoke_agent_runtime",
            {
                "response": _streaming(json.dumps(result).encode()),
                "contentType": "application/json",
                "statusCode": 200,
            },
            {
                "agentRuntimeArn": ARN,
                "runtimeSessionId": session_id,
                "contentType": "application/json",
                "accept": "application/json",
                "payload": json.dumps(payload).encode(),
            },
        )
        assert (
            AgentCoreClient(runtime_arn=ARN, client=client).invoke(payload, session_id)
            == result
        )


def test_invoke_wraps_service_errors() -> None:
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    with Stubber(client) as stub:
        stub.add_client_error("invoke_agent_runtime", "ThrottlingException")
        with pytest.raises(AgentInvocationError):
            AgentCoreClient(runtime_arn=ARN, client=client).invoke(
                {}, session_id_for_case("CASE-1")
            )


def test_session_id_is_stable_and_long_enough() -> None:
    assert session_id_for_case("CASE-1") == session_id_for_case("CASE-1")
    assert len(session_id_for_case("CASE-1")) >= 33
    assert session_id_for_case("CASE-1").startswith("case-CASE-1-")
