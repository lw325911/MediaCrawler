# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
Account selection and health tracking.

* ``acquire`` hands out the available account that was used least recently.
* ``report_failure`` puts the account into an exponential cooldown
  (cooldown_sec * 2^(fails-1), capped at 24h) and marks it INVALID once it
  reaches ``max_fails`` consecutive failures.
* ``report_success`` resets the failure counter.
"""
import time
from typing import Optional

from .models import AccountInfo, AccountStatus
from .store import AccountStore

MAX_COOLDOWN_SEC = 24 * 3600


class AccountPool:
    def __init__(self, store: AccountStore, platform: str, cooldown_sec: int = 600, max_fails: int = 3):
        self.store = store
        self.platform = platform
        self.cooldown_sec = cooldown_sec
        self.max_fails = max_fails

    def available(self, now: Optional[float] = None):
        now = time.time() if now is None else now
        return [a for a in self.store.list(self.platform) if a.is_available(now)]

    def acquire(self, now: Optional[float] = None) -> Optional[AccountInfo]:
        now = time.time() if now is None else now
        candidates = self.available(now)
        if not candidates:
            return None
        account = min(candidates, key=lambda a: (a.last_used_at, a.created_at))
        account.last_used_at = now
        self.store.upsert(account)
        return account

    def report_success(self, account: AccountInfo) -> None:
        acc = self.store.get(account.id) or account
        acc.fail_count = 0
        acc.last_error = ""
        acc.cooling_until = 0
        self.store.upsert(acc)

    def report_failure(self, account: AccountInfo, reason: str = "", now: Optional[float] = None) -> AccountInfo:
        now = time.time() if now is None else now
        acc = self.store.get(account.id) or account
        acc.fail_count += 1
        acc.last_error = (reason or "")[:500]
        if acc.fail_count >= self.max_fails:
            acc.status = AccountStatus.INVALID
        else:
            delay = min(self.cooldown_sec * (2 ** (acc.fail_count - 1)), MAX_COOLDOWN_SEC)
            acc.cooling_until = now + delay
        self.store.upsert(acc)
        return acc

    def next_available_at(self) -> Optional[float]:
        """When the earliest cooling account becomes usable again (None if none will)."""
        waits = [a.cooling_until for a in self.store.list(self.platform) if a.status == AccountStatus.NORMAL]
        return min(waits) if waits else None
