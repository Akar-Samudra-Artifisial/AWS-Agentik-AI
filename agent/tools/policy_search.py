"""``search_policy`` with Bedrock Knowledge Base retrieval and a static fallback.

Primary: ``bedrock-agent-runtime.retrieve`` (top-k 4) via an injected
``PolicyRetriever`` (``BedrockKnowledgeBaseRetriever``). Fallback (RAG-006): keyword
scoring over the local ``rag/policies/*.md`` documents, used when no retriever is
configured, the KB errors/times out, or returns nothing.
"""

import functools
import os
import re
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from resolveai_common.logging import get_logger

from ..context import ToolContext
from .base import ToolError, ok
from .registry import logged_tool

__all__ = [
    "TOP_K",
    "BedrockKnowledgeBaseRetriever",
    "default_policy_dir",
    "search_policy",
    "static_search",
]

TOP_K = 4
MAX_QUERY_CHARS = 500
# RAG-006: treat the KB as unavailable beyond 5 seconds.
KB_TIMEOUT_SECONDS = 5

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "yang", "dan", "atau", "untuk", "dengan", "dari", "pada", "dalam", "akan", "ini",
        "itu", "ada", "tidak", "bisa", "sudah", "apa", "berapa", "kapan", "bagaimana",
        "boleh", "saya", "kami", "anda", "the", "and", "for", "with", "what", "when", "how",
    }
)  # fmt: skip


class BedrockKnowledgeBaseRetriever:
    """``PolicyRetriever`` backed by Bedrock Knowledge Bases ``Retrieve``."""

    def __init__(self, knowledge_base_id: str, client: Any | None = None) -> None:
        self._kb_id = knowledge_base_id
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = boto3.client(
                "bedrock-agent-runtime",
                config=Config(
                    connect_timeout=2,
                    read_timeout=KB_TIMEOUT_SECONDS,
                    retries={"max_attempts": 1},
                ),
            )
        return self._client

    def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        resp = self._get_client().retrieve(
            knowledgeBaseId=self._kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": top_k}
            },
        )
        results: list[dict[str, Any]] = []
        for item in resp.get("retrievalResults", []):
            uri = item.get("location", {}).get("s3Location", {}).get("uri", "")
            results.append(
                {
                    "text": item.get("content", {}).get("text", ""),
                    "source": Path(uri).stem if uri else "unknown",
                    "score": round(float(item.get("score", 0.0)), 3),
                }
            )
        return results[:top_k]


def default_policy_dir() -> Path:
    override = os.environ.get("POLICY_DOCS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "rag" / "policies"


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in _TOKEN_RE.findall(text.lower())
        if len(t) >= 3 and t not in _STOPWORDS
    }


def _strip_front_matter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip()
    return text


@functools.lru_cache(maxsize=4)
def _load_chunks(policy_dir: str) -> tuple[tuple[str, str], ...]:
    """Split each policy document into ``(source, text)`` chunks per ``##`` section."""
    chunks: list[tuple[str, str]] = []
    for path in sorted(Path(policy_dir).glob("*.md")):
        body = _strip_front_matter(path.read_text(encoding="utf-8"))
        title, _, rest = body.partition("\n")
        sections = re.split(r"\n(?=## )", rest)
        for section in sections:
            text = section.strip()
            if text:
                chunks.append((path.stem, f"{title.strip()}\n{text}"))
    return tuple(chunks)


def static_search(
    query: str, top_k: int = TOP_K, policy_dir: Path | None = None
) -> list[dict]:
    """Keyword-overlap search over the local policy documents (fallback)."""
    query_tokens = _tokens(query)
    if not query_tokens:
        return []
    scored: list[dict[str, Any]] = []
    for source, text in _load_chunks(str(policy_dir or default_policy_dir())):
        hits = query_tokens & (_tokens(text) | _tokens(source.replace("-", " ")))
        if hits:
            score = round(len(hits) / len(query_tokens), 3)
            scored.append({"text": text, "source": source, "score": score})
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:top_k]


@logged_tool
def search_policy(ctx: ToolContext, query: str) -> dict[str, Any]:
    """Cari kebijakan toko yang relevan (keterlambatan, paket hilang, refund, eskalasi, dll).

    Search the store policy knowledge base. Call this before offering any compensation
    or explaining a rule, and base decisions only on the returned text.

    Args:
        query: Natural-language question, e.g. "pesanan terlambat 2 hari kompensasi".

    Returns:
        ``{ok, results: [{text, source, score}], retrieval}`` with up to 4 passages;
        ``retrieval`` is "knowledge_base" or "static_fallback".
    """
    query = query.strip()
    if not query or len(query) > MAX_QUERY_CHARS:
        raise ToolError(
            "invalid_input", f"query wajib diisi, maks {MAX_QUERY_CHARS} karakter"
        )

    if ctx.policy_retriever is not None:
        try:
            results = ctx.policy_retriever.retrieve(query, TOP_K)
        except Exception as exc:  # noqa: BLE001 - any KB failure falls back (RAG-006)
            get_logger(__name__, ctx.case_id).warning(
                "knowledge base retrieve failed, using static fallback",
                extra={"error": str(exc)},
            )
            results = []
        if results:
            return ok(results=results[:TOP_K], retrieval="knowledge_base")
    return ok(results=static_search(query), retrieval="static_fallback")
