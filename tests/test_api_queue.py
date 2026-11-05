# -*- coding: utf-8 -*-
import asyncio

import pytest

from api.schemas import CrawlerStartRequest, PlatformEnum
from api.services.crawler_manager import CrawlerManager


class FakeProc:
    def __init__(self):
        self.done = False

    def poll(self):
        return 0 if self.done else None


@pytest.mark.asyncio
async def test_queue_runs_tasks_in_order(monkeypatch):
    cm = CrawlerManager()
    started = []

    async def fake_start(config):
        started.append(config.keywords)
        cm.process = FakeProc()
        cm.status = "running"
        return True

    monkeypatch.setattr(cm, "start", fake_start)
    req = lambda k: CrawlerStartRequest(platform=PlatformEnum.XHS, keywords=k)

    r1 = await cm.enqueue(req("a"))
    await cm.enqueue(req("b"))
    r3 = await cm.enqueue(req("c"))
    assert started == ["a"]
    assert [t["keywords"] for t in cm.list_queue()] == ["b", "c"]

    assert cm.remove_from_queue(r3["task_id"])
    assert not cm.remove_from_queue(r1["task_id"])  # already started

    # current task finishes -> next starts
    cm.process.done = True
    cm.status = "idle"
    cm._schedule_next()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert started == ["a", "b"]
    assert cm.list_queue() == []
    assert cm.clear_queue() == 0
