# -*- coding: utf-8 -*-
import shutil

import httpx
import pytest
from fastapi.testclient import TestClient

import config
from sign_service.server import app
from sign_service.client import SignServiceError

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@pytest.fixture
def srv(monkeypatch):
    client = TestClient(app)

    def fake_post(url, json=None, headers=None, timeout=None, trust_env=None):
        path = url.split("http://signsrv", 1)[1]
        return client.post(path, json=json, headers=headers or {})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(config, "SIGN_SRV_URL", "http://signsrv", raising=False)
    monkeypatch.setattr(config, "SIGN_SRV_TOKEN", "", raising=False)
    monkeypatch.delenv("SIGN_SRV_TOKEN", raising=False)
    return client


def test_health(srv):
    assert srv.get("/signsrv/health").json()["platforms"] == ["dy", "xhs", "zhihu"]


def test_xhs_remote_matches_shape(srv):
    from media_platform.xhs.playwright_sign import sign_with_xhshow

    res = sign_with_xhshow("/api/sns/web/v1/search/notes", {"keyword": "k"}, "a1=abc; web_session=1", "POST")
    assert set(res) == {"x-s", "x-t", "x-s-common", "x-b3-traceid"} and res["x-s"]


@needs_node
def test_dy_remote(srv):
    from media_platform.douyin.help import get_a_bogus_from_js

    assert get_a_bogus_from_js("https://www.douyin.com/aweme/v1/web/aweme/detail/", "aweme_id=1", UA)


def test_errors(srv, monkeypatch):
    assert srv.post("/signsrv/v1/nope", json={}).status_code == 404
    assert srv.post("/signsrv/v1/dy", json={}).json()["ok"] is False
    from sign_service.client import remote_sign

    with pytest.raises(SignServiceError):
        remote_sign("dy", {})
    monkeypatch.setenv("SIGN_SRV_TOKEN", "t")
    assert srv.post("/signsrv/v1/xhs", json={"uri": "/x"}).status_code == 401
    monkeypatch.setattr(config, "SIGN_SRV_TOKEN", "t", raising=False)
    assert remote_sign("xhs", {"uri": "/x", "data": {}, "cookie_str": "a1=1", "method": "GET"})["x-s"]


def test_local_when_not_configured(monkeypatch):
    monkeypatch.setattr(config, "SIGN_SRV_URL", "", raising=False)

    def boom(*a, **k):
        raise AssertionError("remote should not be called")

    monkeypatch.setattr(httpx, "post", boom)
    from media_platform.xhs.playwright_sign import sign_with_xhshow

    assert sign_with_xhshow("/x", {}, "a1=1", "GET")["x-s"]
