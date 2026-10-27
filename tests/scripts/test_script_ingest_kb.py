"""Offline tests for scripts/ingest_kb.py and the shared config resolver (RAG-004)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import boto3
import ingest_kb
import pytest
from _config import ConfigError, resolve_config
from botocore.stub import Stubber
from moto import mock_aws

_BUCKET = "kb-docs-test"


def _job(status: str, **extra: object) -> dict:
    return {
        "ingestionJob": {
            "knowledgeBaseId": "KB1",
            "dataSourceId": "DS1",
            "ingestionJobId": "JOB1",
            "status": status,
            "startedAt": "2026-10-27T00:00:00Z",
            "updatedAt": "2026-10-27T00:00:00Z",
            **extra,
        }
    }


@pytest.fixture
def agent_stub() -> Iterator[tuple[object, Stubber]]:
    client = boto3.client("bedrock-agent", region_name="us-east-1")
    with Stubber(client) as stub:
        yield client, stub
        stub.assert_no_pending_responses()


def test_parse_front_matter() -> None:
    text = "---\ndoc_type: refund-policy\nversion: 1\n---\n# Judul\n"
    assert ingest_kb.parse_front_matter(text) == {
        "doc_type": "refund-policy",
        "version": 1,
    }
    assert ingest_kb.parse_front_matter("# tanpa front matter") == {}
    assert ingest_kb.parse_front_matter("---\nbelum ditutup") == {}


def test_build_uploads_real_policies_have_metadata_sidecars() -> None:
    uploads = ingest_kb.build_uploads(ingest_kb.DEFAULT_DOCS_DIR, "docs/")
    docs = [u for u in uploads if u.key.endswith(".md")]
    sidecars = {
        u.key: json.loads(u.body) for u in uploads if u.key.endswith(".metadata.json")
    }
    assert len(docs) == 7
    assert len(sidecars) == 7
    refund = sidecars["docs/refund-policy.md.metadata.json"]
    assert refund["metadataAttributes"]["doc_type"] == "refund-policy"


def test_build_uploads_falls_back_to_file_stem(tmp_path: Path) -> None:
    (tmp_path / "faq.md").write_text("# FAQ\n", encoding="utf-8")
    uploads = ingest_kb.build_uploads(tmp_path)
    meta = json.loads(uploads[1].body)
    assert meta == {"metadataAttributes": {"doc_type": "faq"}}


def test_build_uploads_empty_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_kb.build_uploads(tmp_path)


@mock_aws
def test_sync_uploads_and_deletes_only_stale_policy_objects() -> None:
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=_BUCKET)
    s3.put_object(Bucket=_BUCKET, Key="old-policy.md", Body=b"x")
    s3.put_object(Bucket=_BUCKET, Key="old-policy.md.metadata.json", Body=b"{}")
    s3.put_object(Bucket=_BUCKET, Key="README.txt", Body=b"keep")
    uploads = ingest_kb.build_uploads(ingest_kb.DEFAULT_DOCS_DIR)

    count, deleted = ingest_kb.sync_to_s3(s3, _BUCKET, uploads)

    keys = {o["Key"] for o in s3.list_objects_v2(Bucket=_BUCKET)["Contents"]}
    assert count == 14
    assert sorted(deleted) == ["old-policy.md", "old-policy.md.metadata.json"]
    assert "README.txt" in keys
    assert "refund-policy.md" in keys
    assert "old-policy.md" not in keys


def test_run_ingestion_polls_until_complete(agent_stub: tuple[object, Stubber]) -> None:
    client, stub = agent_stub
    ids = {"knowledgeBaseId": "KB1", "dataSourceId": "DS1"}
    stub.add_response(
        "start_ingestion_job",
        _job("STARTING"),
        {**ids, "description": "scripts/ingest_kb.py"},
    )
    stub.add_response(
        "get_ingestion_job", _job("IN_PROGRESS"), {**ids, "ingestionJobId": "JOB1"}
    )
    stub.add_response(
        "get_ingestion_job",
        _job("COMPLETE", statistics={"numberOfDocumentsFailed": 0}),
        {**ids, "ingestionJobId": "JOB1"},
    )
    sleeps: list[float] = []

    job = ingest_kb.run_ingestion(
        client, "KB1", "DS1", timeout=60, poll=5, sleep=sleeps.append, clock=lambda: 0.0
    )

    assert job["status"] == "COMPLETE"
    assert sleeps == [5, 5]


def test_run_ingestion_times_out(agent_stub: tuple[object, Stubber]) -> None:
    client, stub = agent_stub
    stub.add_response("start_ingestion_job", _job("IN_PROGRESS"))
    ticks = iter([0.0, 100.0])
    with pytest.raises(TimeoutError, match="JOB1"):
        ingest_kb.run_ingestion(
            client,
            "KB1",
            "DS1",
            timeout=10,
            poll=1,
            sleep=lambda _: None,
            clock=lambda: next(ticks),
        )


def test_resolve_data_source(agent_stub: tuple[object, Stubber]) -> None:
    client, stub = agent_stub
    summary = {"knowledgeBaseId": "KB1", "name": "s3", "status": "AVAILABLE",
               "updatedAt": "2026-10-27T00:00:00Z"}  # fmt: skip
    stub.add_response(
        "list_data_sources",
        {"dataSourceSummaries": [{**summary, "dataSourceId": "DS9"}]},
    )
    stub.add_response(
        "list_data_sources",
        {
            "dataSourceSummaries": [
                {**summary, "dataSourceId": "A"},
                {**summary, "dataSourceId": "B"},
            ]
        },
    )
    assert ingest_kb.resolve_data_source(client, "KB1", "GIVEN") == "GIVEN"
    assert ingest_kb.resolve_data_source(client, "KB1", None) == "DS9"
    with pytest.raises(ConfigError, match="2 data source"):
        ingest_kb.resolve_data_source(client, "KB1", None)


def test_main_dry_run_is_offline(capsys: pytest.CaptureFixture[str]) -> None:
    assert ingest_kb.main(["--dry-run"]) == 0
    assert "7 dokumen" in capsys.readouterr().out


def test_resolve_config_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOME_VAR", "from-env")
    assert resolve_config("from-arg", "SOME_VAR") == "from-arg"
    assert resolve_config(None, "SOME_VAR") == "from-env"
    monkeypatch.delenv("SOME_VAR")
    with pytest.raises(ConfigError, match="SOME_VAR"):
        resolve_config(None, "SOME_VAR")


def test_resolve_config_reads_ssm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("RESOLVEAI_SSM_PREFIX", "/resolveai/test")
    ssm = boto3.client("ssm", region_name="us-east-1")
    with Stubber(ssm) as stub:
        stub.add_response(
            "get_parameter",
            {"Parameter": {"Name": "/resolveai/test/api/key", "Value": "s3cret"}},
            {"Name": "/resolveai/test/api/key", "WithDecryption": True},
        )
        stub.add_client_error("get_parameter", "ParameterNotFound")
        assert resolve_config(None, "API_KEY", "api/key", ssm_client=ssm) == "s3cret"
        with pytest.raises(ConfigError, match="/resolveai/test/api/key"):
            resolve_config(None, "API_KEY", "api/key", ssm_client=ssm)
