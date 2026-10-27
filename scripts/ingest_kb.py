#!/usr/bin/env python3
"""Sync ``rag/policies/*.md`` to the kb-docs bucket and run a KB ingestion job (RAG-004).

Each document is uploaded with a ``<file>.metadata.json`` sidecar carrying ``doc_type``
from its YAML front matter (RAG-003), stale ``.md``/sidecar objects under the prefix
are deleted, then ``bedrock-agent.start_ingestion_job`` is started and polled until it
completes. Exit code 0 only when the job is ``COMPLETE`` with no failed documents.

Configuration (argument → env → SSM ``/resolveai/dev/...``):
    --bucket          KB_DOCS_BUCKET        kb/docs_bucket
    --kb-id           KNOWLEDGE_BASE_ID     kb/id
    --data-source-id  KB_DATA_SOURCE_ID     kb/data_source_id (else the KB's only data source)

Examples:
    python scripts/ingest_kb.py --dry-run
    KB_DOCS_BUCKET=resolveai-dev-kb-docs python scripts/ingest_kb.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from _config import REPO_ROOT, ConfigError, resolve_config

__all__ = ["Upload", "build_uploads", "main", "parse_front_matter", "run_ingestion"]

DEFAULT_DOCS_DIR = REPO_ROOT / "rag" / "policies"
_METADATA_SUFFIX = ".metadata.json"
_FINAL_STATUSES = frozenset({"COMPLETE", "FAILED", "STOPPED"})


@dataclass(frozen=True)
class Upload:
    key: str
    body: bytes
    content_type: str


def parse_front_matter(text: str) -> dict[str, Any]:
    """Return the YAML front matter of a markdown document (``{}`` when absent)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    data = yaml.safe_load(text[3:end])
    return data if isinstance(data, dict) else {}


def build_uploads(docs_dir: Path, prefix: str = "") -> list[Upload]:
    """Documents plus their Bedrock KB metadata sidecars, sorted by key."""
    paths = sorted(docs_dir.glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"tidak ada dokumen *.md di {docs_dir}")
    uploads: list[Upload] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        meta = parse_front_matter(text)
        key = f"{prefix}{path.name}"
        attributes = {"doc_type": str(meta.get("doc_type") or path.stem)}
        if meta.get("version") is not None:
            attributes["version"] = str(meta["version"])
        uploads.append(
            Upload(key, text.encode("utf-8"), "text/markdown; charset=utf-8")
        )
        uploads.append(
            Upload(
                key + _METADATA_SUFFIX,
                json.dumps({"metadataAttributes": attributes}).encode("utf-8"),
                "application/json",
            )
        )
    return uploads


def sync_to_s3(
    s3: Any, bucket: str, uploads: Sequence[Upload], prefix: str = ""
) -> tuple[int, list[str]]:
    """Upload ``uploads`` and delete stale policy objects under ``prefix``."""
    wanted = {u.key for u in uploads}
    for upload in uploads:
        s3.put_object(
            Bucket=bucket,
            Key=upload.key,
            Body=upload.body,
            ContentType=upload.content_type,
        )
    stale: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix
    ):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            is_policy = key.endswith((".md", ".md" + _METADATA_SUFFIX))
            if is_policy and key not in wanted:
                stale.append(key)
    for key in stale:
        s3.delete_object(Bucket=bucket, Key=key)
    return len(uploads), stale


def resolve_data_source(agent: Any, kb_id: str, data_source_id: str | None) -> str:
    if data_source_id:
        return data_source_id
    summaries = agent.list_data_sources(knowledgeBaseId=kb_id).get(
        "dataSourceSummaries", []
    )
    if len(summaries) != 1:
        raise ConfigError(
            f"KB {kb_id} punya {len(summaries)} data source; set KB_DATA_SOURCE_ID"
        )
    return str(summaries[0]["dataSourceId"])


def run_ingestion(
    agent: Any,
    kb_id: str,
    data_source_id: str,
    *,
    timeout: float,
    poll: float,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Start an ingestion job and poll it until a final status; return the job."""
    job = agent.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id,
        description="scripts/ingest_kb.py",
    )["ingestionJob"]
    deadline = clock() + timeout
    while job["status"] not in _FINAL_STATUSES:
        if clock() >= deadline:
            raise TimeoutError(
                f"ingestion job {job['ingestionJobId']} masih {job['status']} "
                f"setelah {timeout:.0f} dtk"
            )
        sleep(poll)
        job = agent.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
            ingestionJobId=job["ingestionJobId"],
        )["ingestionJob"]
    return job


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync dokumen kebijakan ke S3 kb-docs dan jalankan ingestion KB."
    )
    parser.add_argument("--bucket", help="bucket kb-docs (env KB_DOCS_BUCKET / SSM)")
    parser.add_argument(
        "--kb-id", help="Knowledge Base ID (env KNOWLEDGE_BASE_ID / SSM kb/id)"
    )
    parser.add_argument(
        "--data-source-id", help="data source ID (env KB_DATA_SOURCE_ID / SSM)"
    )
    parser.add_argument(
        "--prefix", default="", help="prefix key S3 (default: root bucket)"
    )
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument(
        "--timeout", type=float, default=900.0, help="detik (default 900)"
    )
    parser.add_argument(
        "--poll", type=float, default=10.0, help="interval polling detik"
    )
    parser.add_argument(
        "--skip-ingest", action="store_true", help="hanya sync S3, tanpa ingestion job"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="tampilkan rencana upload saja (offline)"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        uploads = build_uploads(args.docs_dir, args.prefix)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    docs = [u.key for u in uploads if u.key.endswith(".md")]
    print(f"{len(docs)} dokumen: {', '.join(docs)}")
    if args.dry_run:
        return 0

    import boto3

    try:
        bucket = resolve_config(args.bucket, "KB_DOCS_BUCKET", "kb/docs_bucket")
        count, deleted = sync_to_s3(boto3.client("s3"), bucket, uploads, args.prefix)
        print(
            f"S3 s3://{bucket}/{args.prefix}: {count} objek diunggah, {len(deleted)} dihapus"
        )
        if args.skip_ingest:
            return 0
        kb_id = resolve_config(args.kb_id, "KNOWLEDGE_BASE_ID", "kb/id")
        agent = boto3.client("bedrock-agent")
        ds_id = args.data_source_id or _optional(
            lambda: resolve_config(None, "KB_DATA_SOURCE_ID", "kb/data_source_id")
        )
        ds_id = resolve_data_source(agent, kb_id, ds_id)
        job = run_ingestion(agent, kb_id, ds_id, timeout=args.timeout, poll=args.poll)
    except (ConfigError, TimeoutError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    stats = job.get("statistics", {})
    print(f"ingestion job {job['ingestionJobId']}: {job['status']}")
    print("statistik: " + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    for reason in job.get("failureReasons", []):
        print(f"  gagal: {reason}", file=sys.stderr)
    if job["status"] != "COMPLETE" or stats.get("numberOfDocumentsFailed", 0):
        return 1
    return 0


def _optional(fn: Callable[[], str]) -> str | None:
    try:
        return fn()
    except ConfigError:
        return None


if __name__ == "__main__":
    sys.exit(main())
