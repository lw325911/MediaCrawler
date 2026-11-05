# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
Run a crawler task with the account pool: pick an account, run, and on
failure switch to the next account and run again. Platforms with checkpoint
support (xhs, dy) continue where the previous account stopped.
"""
import asyncio
import time
from typing import Awaitable, Callable, Dict, Optional

import config
from tools import utils

from .models import AccountInfo
from .pool import AccountPool
from .store import AccountStore

# Config keys an account temporarily overrides; restored after the run.
_OVERRIDDEN_KEYS = (
    "LOGIN_TYPE", "COOKIES", "USER_DATA_DIR", "ENABLE_CDP_MODE",
    "ENABLE_IP_PROXY", "IP_PROXY_PROVIDER_NAME", "STATIC_PROXY_URL",
)


class NoAccountAvailableError(RuntimeError):
    pass


def build_pool(platform: str) -> AccountPool:
    store = AccountStore(getattr(config, "ACCOUNT_POOL_FILE", "data/accounts/accounts.json"))
    return AccountPool(
        store,
        platform,
        cooldown_sec=int(getattr(config, "ACCOUNT_COOLDOWN_SEC", 600)),
        max_fails=int(getattr(config, "ACCOUNT_MAX_FAILS", 3)),
    )


def apply_account(account: AccountInfo, base: Dict[str, object]) -> None:
    """Point the global config at ``account``. ``base`` is the config before any account."""
    for key, value in base.items():
        setattr(config, key, value)
    config.LOGIN_TYPE = "cookie"
    config.COOKIES = account.cookies
    # Separate browser profile per account, otherwise a saved login of another
    # account would be reused and the cookie never applied.
    config.USER_DATA_DIR = f"%s_user_data_dir_acc_{account.id}"
    # CDP mode attaches to the user's own Chrome; injecting pool cookies there
    # would overwrite their personal login, so pool runs use a managed browser.
    config.ENABLE_CDP_MODE = False
    if account.proxy:
        config.ENABLE_IP_PROXY = True
        config.IP_PROXY_PROVIDER_NAME = "static"
        config.STATIC_PROXY_URL = account.proxy


async def run_with_account_pool(
    run_once: Callable[[], Awaitable[bool]],
    pool: Optional[AccountPool] = None,
    max_switches: Optional[int] = None,
    wait_for_cooldown: Optional[bool] = None,
) -> AccountInfo:
    """
    ``run_once`` runs the crawler for the currently applied account and returns
    True when the task completed, False when it stopped early (blocked,
    interrupted). Exceptions also count as a failure of that account.

    Returns the account that completed the task. Raises NoAccountAvailableError
    when every account failed or is cooling down.
    """
    pool = pool or build_pool(config.PLATFORM)
    if max_switches is None:
        max_switches = int(getattr(config, "ACCOUNT_MAX_SWITCHES", 0)) or len(pool.store.list(pool.platform)) * 2 or 1
    if wait_for_cooldown is None:
        wait_for_cooldown = bool(getattr(config, "ACCOUNT_WAIT_FOR_COOLDOWN", False))

    base = {key: getattr(config, key) for key in _OVERRIDDEN_KEYS}
    attempts = 0
    try:
        while attempts < max_switches:
            account = pool.acquire()
            if account is None:
                next_at = pool.next_available_at()
                if wait_for_cooldown and next_at and next_at > time.time():
                    wait = next_at - time.time() + 1
                    utils.logger.warning(f"[AccountPool] 没有可用账号，等待 {int(wait)} 秒冷却结束")
                    await asyncio.sleep(wait)
                    continue
                raise NoAccountAvailableError(
                    f"平台 {pool.platform} 没有可用账号，请添加账号或在账号管理中重置失效账号"
                )
            attempts += 1
            apply_account(account, base)
            utils.logger.info(
                f"[AccountPool] 使用账号 {account.account_name or account.id} ({account.id})"
                f"{'，绑定代理' if account.proxy else ''}，第 {attempts} 次尝试"
            )
            try:
                completed = await run_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - any crawler error rotates the account
                acc = pool.report_failure(account, f"{type(e).__name__}: {e}")
                utils.logger.error(
                    f"[AccountPool] 账号 {account.id} 运行出错，切换下一个账号 (失败 {acc.fail_count} 次, 状态 {acc.status.value}): {e}"
                )
                continue
            if completed:
                pool.report_success(account)
                return account
            acc = pool.report_failure(account, "task stopped early (blocked or data fetch error)")
            utils.logger.warning(
                f"[AccountPool] 账号 {account.id} 未完成任务，切换下一个账号继续 (失败 {acc.fail_count} 次, 状态 {acc.status.value})"
            )
        raise NoAccountAvailableError(f"已切换 {attempts} 次账号仍未完成任务")
    finally:
        for key, value in base.items():
            setattr(config, key, value)
