# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
Hot search list fetchers.

| platform | login cookie | endpoint |
| dy       | not needed   | www.douyin.com/aweme/v1/web/hot/search/list/ (a_bogus signed) |
| bili     | not needed   | s.search.bilibili.com/main/hotword |
| wb       | required     | weibo.com/ajax/side/hotSearch |
| zhihu    | required     | www.zhihu.com/api/v3/feed/topstory/hot-lists/total |

xhs has no public hot search list.
"""
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional

import httpx

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


class HotSearchError(RuntimeError):
    pass


@dataclass
class HotItem:
    platform: str
    rank: int
    word: str
    hot_value: int = 0
    url: str = ""
    label: str = ""
    crawled_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict:
        return asdict(self)


def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------- parsers
# Kept separate from the HTTP calls so they can be unit tested on fixtures.

def parse_dy(body: Dict) -> List[HotItem]:
    words = (body.get("data") or {}).get("word_list") or []
    items = []
    for i, w in enumerate(words, start=1):
        word = w.get("word", "")
        items.append(HotItem(
            platform="dy", rank=i, word=word, hot_value=_int(w.get("hot_value")),
            url=f"https://www.douyin.com/search/{urllib.parse.quote(word)}" if word else "",
            label="置顶" if w.get("is_n1") else "",
        ))
    return items


def parse_bili(body: Dict) -> List[HotItem]:
    if body.get("code") != 0:
        raise HotSearchError(f"bilibili hotword error: {body.get('code')}")
    items = []
    for i, w in enumerate(body.get("list") or [], start=1):
        word = w.get("keyword") or w.get("show_name") or ""
        items.append(HotItem(
            platform="bili", rank=_int(w.get("pos")) or i, word=w.get("show_name") or word,
            hot_value=_int(w.get("heat_score") or w.get("score")),
            url=f"https://search.bilibili.com/all?keyword={urllib.parse.quote(word)}" if word else "",
        ))
    return items


def parse_wb(body: Dict) -> List[HotItem]:
    if body.get("ok") != 1:
        raise HotSearchError(f"weibo hotSearch error (需要登录 cookie): {str(body)[:200]}")
    items = []
    realtime = [r for r in (body.get("data") or {}).get("realtime") or [] if not r.get("is_ad")]
    for i, r in enumerate(realtime, start=1):
        word = r.get("word") or r.get("note") or ""
        items.append(HotItem(
            platform="wb", rank=_int(r.get("rank")) + 1 if r.get("rank") is not None else i, word=word,
            hot_value=_int(r.get("num") or r.get("raw_hot")),
            url=f"https://s.weibo.com/weibo?q={urllib.parse.quote('#' + word + '#')}" if word else "",
            label=r.get("label_name") or "",
        ))
    return items


def parse_zhihu(body: Dict) -> List[HotItem]:
    if "error" in body:
        raise HotSearchError(f"zhihu hot list error (需要登录 cookie): {body['error']}")
    items = []
    for i, d in enumerate(body.get("data") or [], start=1):
        target = d.get("target") or {}
        text = d.get("detail_text") or ""  # "1234 万热度"
        hot = 0
        num = text.split(" ")[0] if text else ""
        if num:
            hot = int(float(num.replace("万", "")) * 10000) if "万" in text else _int(num)
        qid = target.get("id")
        items.append(HotItem(
            platform="zhihu", rank=i, word=target.get("title", ""), hot_value=hot,
            url=f"https://www.zhihu.com/question/{qid}" if qid else "",
        ))
    return items


# ---------------------------------------------------------------- fetchers

async def _get_json(client: httpx.AsyncClient, url: str, **kw) -> Dict:
    resp = await client.get(url, **kw)
    if resp.status_code != 200:
        raise HotSearchError(f"{url} -> HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as e:
        raise HotSearchError(f"{url} 返回的不是 JSON（可能被风控或需要登录）") from e


async def fetch_dy(client: httpx.AsyncClient, cookies: str) -> List[HotItem]:
    from media_platform.douyin.help import get_a_bogus_from_js

    url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
    params = {
        "device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web", "detail_list": "1",
        "source": "6", "pc_client_type": "1", "version_code": "170400", "version_name": "17.4.0",
        "cookie_enabled": "true", "platform": "PC", "downlink": "10",
    }
    query = urllib.parse.urlencode(params)
    a_bogus = get_a_bogus_from_js(url, query, UA)
    body = await _get_json(
        client, f"{url}?{query}&a_bogus={urllib.parse.quote(a_bogus)}",
        headers={"Referer": "https://www.douyin.com/hot", **({"Cookie": cookies} if cookies else {})},
    )
    if not (body.get("data") or {}).get("word_list"):
        raise HotSearchError(f"douyin hot list empty: {str(body)[:200]}")
    return parse_dy(body)


async def fetch_bili(client: httpx.AsyncClient, cookies: str) -> List[HotItem]:
    body = await _get_json(client, "https://s.search.bilibili.com/main/hotword",
                           headers={"Referer": "https://www.bilibili.com/", **({"Cookie": cookies} if cookies else {})})
    return parse_bili(body)


async def fetch_wb(client: httpx.AsyncClient, cookies: str) -> List[HotItem]:
    if not cookies:
        raise HotSearchError("微博热搜需要登录 cookie（--cookies 或账号池）")
    body = await _get_json(client, "https://weibo.com/ajax/side/hotSearch",
                           headers={"Referer": "https://weibo.com/", "Cookie": cookies})
    return parse_wb(body)


async def fetch_zhihu(client: httpx.AsyncClient, cookies: str) -> List[HotItem]:
    if not cookies:
        raise HotSearchError("知乎热榜需要登录 cookie（--cookies 或账号池）")
    body = await _get_json(client, "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50",
                           headers={"Referer": "https://www.zhihu.com/hot", "Cookie": cookies})
    return parse_zhihu(body)


FETCHERS: Dict[str, Callable[[httpx.AsyncClient, str], Awaitable[List[HotItem]]]] = {
    "dy": fetch_dy,
    "bili": fetch_bili,
    "wb": fetch_wb,
    "zhihu": fetch_zhihu,
}


async def fetch_hot_search(platform: str, cookies: str = "", proxy: Optional[str] = None) -> List[HotItem]:
    fetcher = FETCHERS.get(platform)
    if fetcher is None:
        raise HotSearchError(f"不支持的平台 {platform}，可选: {', '.join(FETCHERS)}")
    async with httpx.AsyncClient(headers={"User-Agent": UA}, proxy=proxy, timeout=20, follow_redirects=True) as client:
        return await fetcher(client, cookies)
