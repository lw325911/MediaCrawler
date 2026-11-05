# -*- coding: utf-8 -*-
"""End-to-end resume behaviour of the xhs / douyin search loops with mocked clients."""
from unittest.mock import AsyncMock

import pytest

import config
from media_platform.douyin.core import DouYinCrawler
from media_platform.xhs.core import XiaoHongShuCrawler
from media_platform.xhs.exception import DataFetchError
from tools.checkpoint import CrawlerCheckpoint


@pytest.fixture
def search_config(monkeypatch):
    monkeypatch.setattr(config, "KEYWORDS", "kw", raising=False)
    monkeypatch.setattr(config, "START_PAGE", 1, raising=False)
    monkeypatch.setattr(config, "CRAWLER_MAX_NOTES_COUNT", 60, raising=False)  # 3 xhs pages
    monkeypatch.setattr(config, "CRAWLER_MAX_SLEEP_SEC", 0, raising=False)
    monkeypatch.setattr(config, "SORT_TYPE", "", raising=False)
    monkeypatch.setattr(config, "PUBLISH_TIME_TYPE", 0, raising=False)
    monkeypatch.setattr(config, "ENABLE_GET_COMMENTS", False, raising=False)


def ckpt(tmp_path, platform):
    return CrawlerCheckpoint(platform, "search", {"k": 1}, checkpoint_dir=str(tmp_path))


def make_xhs(tmp_path, client, monkeypatch):
    crawler = XiaoHongShuCrawler.__new__(XiaoHongShuCrawler)
    crawler.xhs_client = client
    crawler.checkpoint = ckpt(tmp_path, "xhs")
    crawler._task_interrupted = False
    crawler.download_media = AsyncMock()
    crawler.get_note_detail_async_task = AsyncMock(side_effect=lambda note_id, **kw: {"note_id": note_id})
    monkeypatch.setattr("media_platform.xhs.core.xhs_store.update_xhs_note", AsyncMock())
    return crawler


@pytest.mark.asyncio
async def test_xhs_search_resumes_after_failure(tmp_path, monkeypatch, search_config):
    def page_res(page):
        return {"has_more": True, "items": [{"id": f"p{page}n{i}"} for i in range(2)]}

    calls = []

    async def failing(keyword, search_id, page, sort):
        calls.append(page)
        if page == 2:
            raise DataFetchError("blocked")
        return page_res(page)

    client = AsyncMock()
    client.get_note_by_keyword.side_effect = failing
    crawler = make_xhs(tmp_path, client, monkeypatch)
    await crawler.search()
    assert calls == [1, 2]
    assert crawler._task_interrupted
    assert crawler.checkpoint.is_page_done("keyword:kw", 1)

    # Second run: page 1 is skipped, pages 2 and 3 are fetched, keyword finished.
    calls.clear()

    async def ok(keyword, search_id, page, sort):
        calls.append(page)
        return page_res(page)

    client2 = AsyncMock()
    client2.get_note_by_keyword.side_effect = ok
    crawler2 = make_xhs(tmp_path, client2, monkeypatch)
    assert crawler2.checkpoint.resumed
    await crawler2.search()
    assert calls == [2, 3]
    assert not crawler2._task_interrupted
    assert crawler2.checkpoint.is_scope_done("keyword:kw")


@pytest.mark.asyncio
async def test_douyin_search_skips_done_pages(tmp_path, monkeypatch, search_config):
    monkeypatch.setattr(config, "CRAWLER_MAX_NOTES_COUNT", 20, raising=False)  # pages 1, 2
    offsets = []

    async def search(keyword, offset, publish_time, search_id):
        offsets.append(offset)
        return {"data": [{"aweme_info": {"aweme_id": f"a{offset}"}}], "extra": {"logid": "x"}}

    client = AsyncMock()
    client.search_info_by_keyword.side_effect = search
    crawler = DouYinCrawler.__new__(DouYinCrawler)
    crawler.dy_client = client
    crawler.checkpoint = ckpt(tmp_path, "dy")
    crawler.checkpoint.mark_page_done("keyword:kw", 1)
    crawler._task_interrupted = False
    crawler.download_media = AsyncMock()
    monkeypatch.setattr("media_platform.douyin.core.douyin_store.update_douyin_aweme", AsyncMock())

    await crawler.search()
    assert offsets == [10]  # only page 2
    assert crawler.checkpoint.is_scope_done("keyword:kw")
    assert not crawler._task_interrupted
