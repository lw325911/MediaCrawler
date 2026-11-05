# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
AI 评论分析（需要 Anthropic API key，评论内容会发送给 Claude API）:

    uv pip install anthropic
    uv run python -m comment_analysis --platform xhs --keyword 编程副业 --limit 500
    uv run python -m comment_analysis --file data/dy/jsonl/search_comments_2026-11-05.jsonl

输出到 {SAVE_DATA_PATH 或 data}/{platform}/analysis/：
  report_<时间>.md（报告）、labeled_<时间>.jsonl（每条评论的标签）、stats_<时间>.json（统计）
"""
import json
import os
import time
from typing import List, Optional

import typer

import config

from .analyzer import DEFAULT_MODEL, AnalysisError, analyze
from .loader import find_comment_files, load_comments

app = typer.Typer(add_completion=False, help="AI 评论分析")


@app.command()
def main(
    platform: str = typer.Option("xhs", "--platform"),
    file: Optional[List[str]] = typer.Option(None, "--file", help="评论文件，可多次指定；不填则读取该平台所有评论文件"),
    keyword: str = typer.Option("", "--keyword", help="只分析该搜索关键词下的评论"),
    post_id: str = typer.Option("", "--post-id", help="只分析某条帖子/视频的评论"),
    limit: int = typer.Option(500, "--limit", help="最多分析多少条（按点赞数从高到低取）"),
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    batch_size: int = typer.Option(40, "--batch-size"),
):
    base = config.SAVE_DATA_PATH or "data"
    paths = file or find_comment_files(platform, base)
    if not paths:
        typer.echo(f"没有找到评论文件（{base}/{platform}/jsonl|json|csv/*comments*）")
        raise typer.Exit(1)
    comments = load_comments(paths, keyword=keyword, post_id=post_id)
    comments.sort(key=lambda c: -c.like_count)
    if limit > 0:
        comments = comments[:limit]
    typer.echo(f"读取 {len(paths)} 个文件，分析 {len(comments)} 条评论，模型 {model}")
    try:
        labeled, stats, report = analyze(
            comments, topic=keyword or post_id, model=model, batch_size=batch_size,
            on_progress=lambda done, total: typer.echo(f"  已标注 {done}/{total}"),
        )
    except AnalysisError as e:
        typer.echo(f"分析失败: {e}")
        raise typer.Exit(1)

    out_dir = os.path.join(base, platform, "analysis")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(out_dir, f"labeled_{ts}.jsonl"), "w", encoding="utf-8") as f:
        for l in labeled:
            f.write(json.dumps(l.to_dict(), ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, f"stats_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    report_path = os.path.join(out_dir, f"report_{ts}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    s = stats["sentiment"]
    typer.echo(
        f"\n正面 {s['positive']['pct']}% / 中性 {s['neutral']['pct']}% / 负面 {s['negative']['pct']}%"
        f"\n报告已保存: {report_path}"
    )


if __name__ == "__main__":
    app()
