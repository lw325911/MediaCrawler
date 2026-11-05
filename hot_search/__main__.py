# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
抓取热搜榜单并保存:

    uv run python -m hot_search --platform dy              # 抖音（无需登录）
    uv run python -m hot_search --platform bili --top 10   # B站
    uv run python -m hot_search --platform wb --cookies "SUB=..."   # 微博/知乎需要 cookie
    uv run python -m hot_search --platform zhihu --use-account-pool # 从账号池取 cookie

保存到 {SAVE_DATA_PATH 或 data}/{platform}/hot_search/hot_search_<时间>.jsonl，
并打印逗号分隔的关键词，可直接用于 main.py --keywords 继续搜索采集。
"""
import asyncio
import json
import os
import time
from typing import Optional

import typer

import config

from .fetchers import FETCHERS, HotSearchError, fetch_hot_search

app = typer.Typer(add_completion=False, help="热搜榜单抓取")


def save_items(platform: str, items, base_dir: Optional[str] = None) -> str:
    base = base_dir or config.SAVE_DATA_PATH or "data"
    out_dir = os.path.join(base, platform, "hot_search")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"hot_search_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")
    return path


@app.command()
def main(
    platform: str = typer.Option(..., "--platform", help=f"可选: {', '.join(FETCHERS)}"),
    cookies: str = typer.Option("", "--cookies"),
    use_account_pool: bool = typer.Option(False, "--use-account-pool", help="从账号池取一个可用账号的 cookie/代理"),
    top: int = typer.Option(0, "--top", help="只保留前 N 条，0 = 全部"),
):
    proxy = None
    if use_account_pool:
        from account_pool.runner import build_pool

        acc = build_pool(platform).acquire()
        if acc is None:
            typer.echo(f"账号池中没有 {platform} 的可用账号")
            raise typer.Exit(1)
        cookies, proxy = acc.cookies, (acc.proxy or None)
    try:
        items = asyncio.run(fetch_hot_search(platform, cookies=cookies, proxy=proxy))
    except HotSearchError as e:
        typer.echo(f"抓取失败: {e}")
        raise typer.Exit(1)
    if top > 0:
        items = items[:top]
    path = save_items(platform, items)
    for it in items:
        typer.echo(f"{it.rank:>3}. {it.word}  {it.hot_value or ''} {it.label}")
    typer.echo(f"\n已保存 {len(items)} 条到 {path}")
    typer.echo("关键词: " + ",".join(it.word.replace(",", " ") for it in items if it.word))


if __name__ == "__main__":
    app()
