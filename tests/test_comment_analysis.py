# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace

import pytest

from comment_analysis.analyzer import AnalysisError, analyze, compute_stats
from comment_analysis.loader import find_comment_files, load_comments


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def test_loader_filters_and_dedupes(tmp_path):
    f = tmp_path / "xhs" / "jsonl" / "search_comments_2026-11-05.jsonl"
    write_jsonl(f, [
        {"comment_id": "1", "note_id": "n1", "content": "好", "like_count": "3", "source_keyword": "k"},
        {"comment_id": "1", "note_id": "n1", "content": "好", "like_count": "3", "source_keyword": "k"},
        {"comment_id": "2", "note_id": "n2", "content": "", "source_keyword": "k"},
        {"comment_id": "3", "note_id": "n2", "content": "差", "source_keyword": "other"},
    ])
    files = find_comment_files("xhs", str(tmp_path))
    assert files == [str(f)]
    comments = load_comments(files, keyword="k")
    assert [(c.id, c.like_count) for c in comments] == [("1", 3)]


class FakeMessages:
    """Mimics client.beta.messages: create() for labels, stream() for the report."""

    def __init__(self, refuse=False):
        self.refuse = refuse
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        assert kw["fallbacks"] == "default" and kw["output_config"]["format"]["type"] == "json_schema"
        n = kw["messages"][0]["content"].count("\n[")
        labels = [{"index": i, "sentiment": ["positive", "negative"][i % 2], "intent": "other", "aspects": ["价格"]}
                  for i in range(n)]
        return SimpleNamespace(stop_reason="refusal" if self.refuse else "end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps({"labels": labels}))])

    def stream(self, **kw):
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="# 报告")])

        class S:
            def __enter__(self_inner):
                return SimpleNamespace(get_final_message=lambda: msg)

            def __exit__(self_inner, *a):
                return False

        return S()


def make_client(**kw):
    return SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(**kw)))


def test_analyze_end_to_end(tmp_path):
    f = tmp_path / "c.jsonl"
    write_jsonl(f, [{"comment_id": str(i), "note_id": "n", "content": f"评论{i}"} for i in range(5)])
    comments = load_comments([str(f)])
    client = make_client()
    labeled, stats, report = analyze(comments, topic="t", client=client, batch_size=2)
    assert len(client.beta.messages.calls) == 3
    assert stats["total"] == 5
    assert stats["sentiment"]["positive"]["count"] == 3  # even index in each batch of 2,2,1
    assert stats["aspects"][0]["aspect"] == "价格" and stats["aspects"][0]["count"] == 5
    assert report == "# 报告"


def test_refusal_raises(tmp_path):
    f = tmp_path / "c.jsonl"
    write_jsonl(f, [{"comment_id": "1", "content": "x"}])
    with pytest.raises(AnalysisError):
        analyze(load_comments([str(f)]), client=make_client(refuse=True))


def test_compute_stats_empty():
    assert compute_stats([])["total"] == 0
