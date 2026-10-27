#!/usr/bin/env python3
"""RAG retrieval eval: hit@4 over ``rag/eval/queries.yaml`` (RAG-007).

For each query the top-4 results are retrieved from the Bedrock Knowledge Base
(``bedrock-agent-runtime.retrieve``) — or, with ``--static``, from the local keyword
fallback used by ``search_policy`` (offline). A query hits when its
``expected_source`` (string or list) is among the top-4 sources. Exit code 1 when
hit@4 is below ``--threshold`` (default 0.9).

Examples:
    python scripts/eval_rag.py --static
    KNOWLEDGE_BASE_ID=XXXX python scripts/eval_rag.py --output docs/evidence/eval_rag.md
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _config import REPO_ROOT, ConfigError, load_yaml, resolve_config

__all__ = ["Query", "QueryResult", "load_queries", "main", "render_report", "score"]

TOP_K = 4
DEFAULT_QUERIES = REPO_ROOT / "rag" / "eval" / "queries.yaml"

Retriever = Callable[[str], list[str]]


@dataclass(frozen=True)
class Query:
    question: str
    expected: tuple[str, ...]


@dataclass(frozen=True)
class QueryResult:
    query: Query
    sources: tuple[str, ...]
    error: str | None = None

    @property
    def hit(self) -> bool:
        return any(src in self.query.expected for src in self.sources[:TOP_K])


def load_queries(path: Path) -> list[Query]:
    """Parse ``{queries: [{question, expected_source}]}``; ``ValueError`` when invalid."""
    data = load_yaml(path)
    items = data.get("queries") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError(f"{path}: kunci 'queries' kosong atau tidak ada")
    queries: list[Query] = []
    for i, item in enumerate(items, start=1):
        question = item.get("question") if isinstance(item, dict) else None
        expected = item.get("expected_source") if isinstance(item, dict) else None
        if isinstance(expected, str):
            expected = [expected]
        if (
            not isinstance(question, str)
            or not question.strip()
            or not isinstance(expected, list)
            or not expected
            or not all(isinstance(e, str) and e for e in expected)
        ):
            raise ValueError(
                f"{path}: entri #{i} butuh 'question' dan 'expected_source'"
            )
        queries.append(Query(question.strip(), tuple(expected)))
    return queries


def score(queries: Sequence[Query], retrieve: Retriever) -> list[QueryResult]:
    """Run every query; a retrieval error counts as a miss and is reported."""
    results: list[QueryResult] = []
    for query in queries:
        try:
            sources = tuple(retrieve(query.question)[:TOP_K])
        except Exception as exc:  # noqa: BLE001 - report and keep evaluating
            results.append(QueryResult(query, (), f"{type(exc).__name__}: {exc}"))
            continue
        results.append(QueryResult(query, sources))
    return results


def hit_rate(results: Sequence[QueryResult]) -> float:
    return sum(r.hit for r in results) / len(results) if results else 0.0


def render_report(results: Sequence[QueryResult], mode: str) -> str:
    rows = [
        f"# Eval RAG — hit@{TOP_K} ({mode})",
        "",
        "| # | Hit | Pertanyaan | Diharapkan | Top-4 sumber |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, start=1):
        got = r.error or ", ".join(r.sources) or "-"
        rows.append(
            f"| {i} | {'YA' if r.hit else 'TIDAK'} | {r.query.question} | "
            f"{' / '.join(r.query.expected)} | {got} |"
        )
    hits = sum(r.hit for r in results)
    rows += ["", f"hit@{TOP_K}: {hits}/{len(results)} = {hit_rate(results):.1%}"]
    return "\n".join(rows)


def static_retriever() -> Retriever:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from agent.tools.policy_search import static_search

    return lambda q: [r["source"] for r in static_search(q, TOP_K)]


def kb_retriever(kb_id: str, client: Any | None = None) -> Retriever:
    if client is None:
        import boto3

        client = boto3.client("bedrock-agent-runtime")

    def retrieve(question: str) -> list[str]:
        resp = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": question},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": TOP_K}
            },
        )
        sources: list[str] = []
        for item in resp.get("retrievalResults", []):
            uri = item.get("location", {}).get("s3Location", {}).get("uri", "")
            sources.append(Path(uri).stem if uri else "unknown")
        return sources

    return retrieve


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hitung hit@4 retrieval kebijakan.")
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument(
        "--static", action="store_true", help="pakai fallback statis lokal (offline)"
    )
    parser.add_argument(
        "--kb-id", help="Knowledge Base ID (env KNOWLEDGE_BASE_ID / SSM kb/id)"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.9, help="ambang lulus (0.9)"
    )
    parser.add_argument(
        "--output", type=Path, help="simpan laporan markdown (docs/evidence/)"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        queries = load_queries(args.queries)
        if args.static:
            retrieve, mode = static_retriever(), "fallback statis"
        else:
            kb_id = resolve_config(args.kb_id, "KNOWLEDGE_BASE_ID", "kb/id")
            retrieve, mode = kb_retriever(kb_id), "Knowledge Base"
    except (ValueError, ConfigError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    results = score(queries, retrieve)
    report = render_report(results, mode)
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    rate = hit_rate(results)
    print(
        f"{'LULUS' if rate >= args.threshold else 'GAGAL'} (ambang {args.threshold:.0%})"
    )
    return 0 if rate >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
