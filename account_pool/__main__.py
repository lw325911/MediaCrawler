# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
账号池命令行管理:

    uv run python -m account_pool list [--platform xhs]
    uv run python -m account_pool add --platform xhs --cookies "a=1; b=2" [--name 小号1] [--proxy http://u:p@ip:port]
    uv run python -m account_pool import accounts.xlsx     # 列: platform, account_name, cookies, proxy, remark
    uv run python -m account_pool reset <id>
    uv run python -m account_pool remove <id>
"""
import json
from typing import Optional

import typer

import config

from .models import AccountInfo
from .store import AccountStore

app = typer.Typer(add_completion=False, help="MediaCrawler 账号池管理")


def _store() -> AccountStore:
    return AccountStore(config.ACCOUNT_POOL_FILE)


@app.command("list")
def list_accounts(platform: Optional[str] = typer.Option(None, "--platform")):
    accounts = _store().list(platform)
    if not accounts:
        typer.echo("账号池为空")
        return
    for a in accounts:
        m = a.masked()
        typer.echo(
            f"{a.id}  {a.platform:<6} {a.account_name or '-':<12} {m['status']:<8} "
            f"可用={'是' if m['available'] else '否'}  失败={a.fail_count}  代理={m['proxy'] or '-'}  {a.last_error[:60]}"
        )


@app.command("add")
def add(
    platform: str = typer.Option(..., "--platform"),
    cookies: str = typer.Option(..., "--cookies"),
    name: str = typer.Option("", "--name"),
    proxy: str = typer.Option("", "--proxy"),
    remark: str = typer.Option("", "--remark"),
):
    acc = AccountInfo(platform=platform, cookies=cookies, account_name=name, proxy=proxy, remark=remark)
    if _store().add_many([acc]) == 0:
        typer.echo("相同平台和 cookie 的账号已存在，未添加")
        raise typer.Exit(1)
    typer.echo(f"已添加账号 {acc.id}")


@app.command("import")
def import_file(path: str):
    accounts = AccountStore.read_import_file(path)
    added = _store().add_many(accounts)
    typer.echo(f"读取 {len(accounts)} 个账号，新增 {added} 个（重复的已跳过）")


@app.command("reset")
def reset(account_id: str):
    if _store().reset(account_id) is None:
        typer.echo("账号不存在")
        raise typer.Exit(1)
    typer.echo("已重置")


@app.command("remove")
def remove(account_id: str):
    if not _store().remove(account_id):
        typer.echo("账号不存在")
        raise typer.Exit(1)
    typer.echo("已删除")


@app.command("export")
def export(platform: Optional[str] = typer.Option(None, "--platform")):
    """Print accounts as JSON (cookies masked)."""
    typer.echo(json.dumps([a.masked() for a in _store().list(platform)], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
