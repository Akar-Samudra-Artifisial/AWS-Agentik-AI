"""Offline tests for scripts/eval_rag.py: YAML loader, hit@4 scoring, static mode (RAG-007)."""

from __future__ import annotations

from pathlib import Path

import boto3
import eval_rag
import pytest
from botocore.stub import Stubber


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "q.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_real_queries_has_at_least_12() -> None:
    queries = eval_rag.load_queries(eval_rag.DEFAULT_QUERIES)
    assert len(queries) >= 12
    assert all(q.expected for q in queries)


def test_load_queries_accepts_list_expected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "queries:\n  - question: Boleh janji refund?\n"
        "    expected_source: [communication-guidelines, refund-policy]\n",
    )
    [query] = eval_rag.load_queries(path)
    assert query.expected == ("communication-guidelines", "refund-policy")


@pytest.mark.parametrize(
    "text",
    ["queries: []\n", "lain: 1\n", "queries:\n  - question: tanpa sumber\n", "- a\n"],
)
def test_load_queries_rejects_invalid(tmp_path: Path, text: str) -> None:
    with pytest.raises(ValueError):
        eval_rag.load_queries(_write(tmp_path, text))


def test_score_hit_only_within_top_4() -> None:
    queries = [
        eval_rag.Query("q1", ("a",)),
        eval_rag.Query("q2", ("e",)),
        eval_rag.Query("q3", ("x", "c")),
    ]
    results = eval_rag.score(
        queries, lambda q: ["b", "c", "d", "b", "e", "a"] if q != "q1" else ["a"]
    )
    assert [r.hit for r in results] == [True, False, True]
    assert eval_rag.hit_rate(results) == pytest.approx(2 / 3)


def test_score_counts_errors_as_miss() -> None:
    def boom(_: str) -> list[str]:
        raise RuntimeError("KB down")

    [result] = eval_rag.score([eval_rag.Query("q", ("a",))], boom)
    assert not result.hit
    assert result.error == "RuntimeError: KB down"
    assert "KB down" in eval_rag.render_report([result], "test")


def test_kb_retriever_maps_s3_uri_to_source() -> None:
    client = boto3.client("bedrock-agent-runtime", region_name="us-east-1")
    with Stubber(client) as stub:
        stub.add_response(
            "retrieve",
            {
                "retrievalResults": [
                    {
                        "content": {"text": "x"},
                        "location": {
                            "type": "S3",
                            "s3Location": {"uri": "s3://kb/refund-policy.md"},
                        },
                        "score": 0.9,
                    },
                    {"content": {"text": "y"}},
                ]
            },
            {
                "knowledgeBaseId": "KBTEST0001",
                "retrievalQuery": {"text": "refund?"},
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {"numberOfResults": 4}
                },
            },
        )
        assert eval_rag.kb_retriever("KBTEST0001", client)("refund?") == [
            "refund-policy",
            "unknown",
        ]


def test_main_static_offline_passes_and_writes_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "evidence" / "eval_rag.md"
    assert eval_rag.main(["--static", "--output", str(out)]) == 0
    assert "hit@4" in capsys.readouterr().out
    assert "fallback statis" in out.read_text(encoding="utf-8")


def test_main_fails_below_threshold(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "queries:\n  - question: voucher maksimal\n    expected_source: tidak-ada\n",
    )
    assert eval_rag.main(["--static", "--queries", str(path)]) == 1


def test_main_without_kb_id_is_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KNOWLEDGE_BASE_ID", raising=False)
    monkeypatch.setattr(
        eval_rag,
        "resolve_config",
        lambda *a, **k: (_ for _ in ()).throw(
            eval_rag.ConfigError("KNOWLEDGE_BASE_ID")
        ),
    )
    assert eval_rag.main([]) == 2
