# -*- coding: utf-8 -*-
import pytest

from hot_search.fetchers import HotSearchError, parse_bili, parse_dy, parse_wb, parse_zhihu
from hot_search.__main__ import save_items


def test_parse_dy():
    body = {"data": {"word_list": [
        {"word": "置顶", "hot_value": 0, "is_n1": True},
        {"word": "热点A", "hot_value": 12164663, "position": 1},
    ]}}
    items = parse_dy(body)
    assert [(i.rank, i.word, i.hot_value, i.label) for i in items] == [(1, "置顶", 0, "置顶"), (2, "热点A", 12164663, "")]
    assert items[1].url.startswith("https://www.douyin.com/search/")


def test_parse_bili():
    items = parse_bili({"code": 0, "list": [{"keyword": "k", "show_name": "展示", "pos": 1, "heat_score": 99}]})
    assert items[0].word == "展示" and items[0].hot_value == 99 and "keyword=k" in items[0].url
    with pytest.raises(HotSearchError):
        parse_bili({"code": -1})


def test_parse_wb_skips_ads():
    body = {"ok": 1, "data": {"realtime": [
        {"word": "A", "num": 100, "rank": 0, "label_name": "热"},
        {"word": "广告", "is_ad": 1},
        {"word": "B", "num": 50, "rank": 1},
    ]}}
    items = parse_wb(body)
    assert [(i.rank, i.word, i.label) for i in items] == [(1, "A", "热"), (2, "B", "")]
    with pytest.raises(HotSearchError):
        parse_wb({"ok": -100})


def test_parse_zhihu():
    body = {"data": [{"detail_text": "1234 万热度", "target": {"id": 1, "title": "问题"}},
                     {"detail_text": "", "target": {"title": "无热度"}}]}
    items = parse_zhihu(body)
    assert items[0].hot_value == 12340000 and items[0].url.endswith("/question/1")
    assert items[1].hot_value == 0
    with pytest.raises(HotSearchError):
        parse_zhihu({"error": {"code": 101}})


def test_save_items(tmp_path):
    path = save_items("bili", parse_bili({"code": 0, "list": [{"keyword": "k"}]}), base_dir=str(tmp_path))
    assert path.startswith(str(tmp_path)) and open(path, encoding="utf-8").read().count("\n") == 1
