# -*- coding: utf-8 -*-
import csv

import pytest

import config
from account_pool import AccountInfo, AccountPool, AccountStatus, AccountStore
from account_pool.runner import NoAccountAvailableError, run_with_account_pool


@pytest.fixture
def store(tmp_path):
    return AccountStore(str(tmp_path / "accounts.json"))


def add(store, n, platform="xhs", **kw):
    accs = [AccountInfo(id=f"a{i}", platform=platform, cookies=f"c={i}", created_at=i, **kw) for i in range(n)]
    store.add_many(accs)
    return accs


def test_acquire_rotates_least_recently_used(store):
    add(store, 3)
    pool = AccountPool(store, "xhs")
    got = [pool.acquire(now=100 + i).id for i in range(4)]
    assert got == ["a0", "a1", "a2", "a0"]


def test_platform_isolation(store):
    add(store, 1, platform="dy")
    assert AccountPool(store, "xhs").acquire() is None


def test_failure_cooldown_and_invalid(store):
    add(store, 1)
    pool = AccountPool(store, "xhs", cooldown_sec=10, max_fails=3)
    acc = pool.acquire(now=0)
    a = pool.report_failure(acc, "x", now=0)
    assert a.cooling_until == 10 and a.status == AccountStatus.NORMAL
    assert pool.acquire(now=5) is None
    assert pool.acquire(now=11) is not None
    a = pool.report_failure(acc, "x", now=11)
    assert a.cooling_until == 31  # 10 * 2
    a = pool.report_failure(acc, "x", now=40)
    assert a.status == AccountStatus.INVALID
    assert pool.acquire(now=10 ** 9) is None
    store.reset(acc.id)
    assert pool.acquire(now=50) is not None


def test_success_clears_failures(store):
    add(store, 1)
    pool = AccountPool(store, "xhs", cooldown_sec=10)
    acc = pool.acquire(now=0)
    pool.report_failure(acc, "x", now=0)
    pool.report_success(acc)
    assert store.get(acc.id).fail_count == 0


def test_duplicates_skipped_and_masking(store):
    add(store, 1, proxy="http://user:secret@1.2.3.4:80")
    assert store.add_many([AccountInfo(platform="xhs", cookies="c=0")]) == 0
    m = store.get("a0").masked()
    assert "secret" not in m["proxy"]


def test_import_csv_and_validation(tmp_path):
    f = tmp_path / "a.csv"
    with open(f, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["platform", "account_name", "cookies", "proxy"])
        w.writerow(["xhs", "小号1", "a=1", ""])
        w.writerow(["dy", "", "b=2", "http://1.1.1.1:8000"])
    accs = AccountStore.read_import_file(str(f))
    assert [a.platform for a in accs] == ["xhs", "dy"]

    bad = tmp_path / "b.csv"
    bad.write_text("platform,cookies\nfoo,a=1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        AccountStore.read_import_file(str(bad))


def test_import_xlsx(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["platform", "cookies", "remark"])
    ws.append(["bili", "SESSDATA=1", "备注"])
    path = tmp_path / "a.xlsx"
    wb.save(path)
    accs = AccountStore.read_import_file(str(path))
    assert accs[0].platform == "bili" and accs[0].remark == "备注"


@pytest.mark.asyncio
async def test_runner_switches_account_and_restores_config(store, monkeypatch):
    add(store, 2)
    store.upsert(store.get("a1").model_copy(update={"proxy": "http://9.9.9.9:1"}))
    monkeypatch.setattr(config, "PLATFORM", "xhs", raising=False)
    monkeypatch.setattr(config, "COOKIES", "orig", raising=False)
    monkeypatch.setattr(config, "ENABLE_IP_PROXY", False, raising=False)
    pool = AccountPool(store, "xhs")
    seen = []

    async def run_once():
        seen.append((config.COOKIES, config.LOGIN_TYPE, config.ENABLE_IP_PROXY, config.STATIC_PROXY_URL,
                     config.USER_DATA_DIR % "xhs"))
        if len(seen) == 1:
            raise RuntimeError("blocked")
        return True

    winner = await run_with_account_pool(run_once, pool=pool)
    assert winner.id == "a1"
    assert seen[0][0] == "c=0" and seen[0][2] is False
    assert seen[1] == ("c=1", "cookie", True, "http://9.9.9.9:1", "xhs_user_data_dir_acc_a1")
    assert store.get("a0").fail_count == 1
    assert config.COOKIES == "orig" and config.ENABLE_IP_PROXY is False


@pytest.mark.asyncio
async def test_runner_gives_up_when_all_fail(store, monkeypatch):
    add(store, 2)
    monkeypatch.setattr(config, "PLATFORM", "xhs", raising=False)
    pool = AccountPool(store, "xhs", cooldown_sec=1000)
    calls = 0

    async def run_once():
        nonlocal calls
        calls += 1
        return False  # stopped early every time

    with pytest.raises(NoAccountAvailableError):
        await run_with_account_pool(run_once, pool=pool, wait_for_cooldown=False)
    assert calls == 2
