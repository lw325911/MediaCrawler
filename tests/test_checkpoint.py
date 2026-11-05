# -*- coding: utf-8 -*-
import json

from tools.checkpoint import CrawlerCheckpoint


def make(tmp_path, inputs=None, enabled=True):
    return CrawlerCheckpoint("xhs", "search", inputs or {"keywords": "a,b"},
                             checkpoint_dir=str(tmp_path), enabled=enabled)


def test_progress_survives_restart(tmp_path):
    ck = make(tmp_path)
    assert not ck.resumed
    ck.mark_page_done("keyword:a", 1)
    ck.mark_items_done("keyword:a", ["n1", "n2"])
    ck.mark_scope_done("keyword:b")

    ck2 = make(tmp_path)
    assert ck2.resumed
    assert ck2.is_page_done("keyword:a", 1)
    assert not ck2.is_page_done("keyword:a", 2)
    assert ck2.filter_pending("keyword:a", ["n1", "n3", "n2"]) == ["n3"]
    assert ck2.is_scope_done("keyword:b")
    assert not ck2.is_scope_done("keyword:a")


def test_different_inputs_use_different_file(tmp_path):
    ck = make(tmp_path, {"keywords": "a"})
    ck.mark_scope_done("keyword:a")
    other = make(tmp_path, {"keywords": "b"})
    assert not other.resumed
    assert ck.path != other.path


def test_finish_removes_file(tmp_path):
    ck = make(tmp_path)
    ck.mark_page_done("keyword:a", 1)
    assert ck.path.exists()
    ck.finish()
    assert not ck.path.exists()
    assert not make(tmp_path).resumed


def test_disabled_writes_nothing(tmp_path):
    ck = make(tmp_path, enabled=False)
    ck.mark_page_done("keyword:a", 1)
    ck.mark_scope_done("keyword:a")
    assert not ck.is_scope_done("keyword:a")
    assert list(tmp_path.iterdir()) == []


def test_corrupt_file_is_ignored(tmp_path):
    ck = make(tmp_path)
    ck.path.parent.mkdir(parents=True, exist_ok=True)
    ck.path.write_text("{not json", encoding="utf-8")
    ck2 = make(tmp_path)
    assert not ck2.resumed
    ck2.mark_page_done("keyword:a", 3)
    assert json.loads(ck2.path.read_text(encoding="utf-8"))["scopes"]["keyword:a"]["pages"] == [3]
