# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient

import config
from api.main import app
from api.services.crawler_manager import CrawlerManager
from api.schemas import CrawlerStartRequest, PlatformEnum


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ACCOUNT_POOL_FILE", str(tmp_path / "acc.json"), raising=False)
    return TestClient(app)


def test_account_crud(client):
    r = client.post("/api/accounts", json={"platform": "xhs", "cookies": "a1=" + "x" * 40, "proxy": "http://u:pw@1.1.1.1:8"})
    assert r.status_code == 200, r.text
    acc = r.json()
    assert "x" * 40 not in acc["cookies"] and "pw" not in acc["proxy"]

    assert client.post("/api/accounts", json={"platform": "xhs", "cookies": "a1=" + "x" * 40}).status_code == 409
    assert client.post("/api/accounts", json={"platform": "nope", "cookies": "a"}).status_code == 400

    r = client.patch(f"/api/accounts/{acc['id']}", json={"status": "disabled"})
    assert r.json()["status"] == "disabled" and r.json()["available"] is False
    r = client.post(f"/api/accounts/{acc['id']}/reset")
    assert r.json()["status"] == "normal"

    assert len(client.get("/api/accounts", params={"platform": "xhs"}).json()["accounts"]) == 1
    assert client.get("/api/accounts", params={"platform": "dy"}).json()["accounts"] == []
    assert client.delete(f"/api/accounts/{acc['id']}").status_code == 200
    assert client.delete(f"/api/accounts/{acc['id']}").status_code == 404


def test_account_import(client):
    body = "platform,cookies\nxhs,a=1\ndy,b=2\n".encode("utf-8")
    r = client.post("/api/accounts/import", params={"filename": "a.csv"}, content=body)
    assert r.json() == {"read": 2, "added": 2}
    r = client.post("/api/accounts/import", params={"filename": "a.csv"}, content=body)
    assert r.json() == {"read": 2, "added": 0}
    assert client.post("/api/accounts/import", params={"filename": "a.txt"}, content=body).status_code == 400
    bad = "platform,cookies\nzzz,a=1\n".encode("utf-8")
    assert client.post("/api/accounts/import", params={"filename": "a.csv"}, content=bad).status_code == 400


def test_build_command_passes_new_flags():
    cmd = CrawlerManager()._build_command(
        CrawlerStartRequest(platform=PlatformEnum.XHS, keywords="k", resume=False, use_account_pool=True)
    )
    assert cmd[cmd.index("--resume") + 1] == "false"
    assert cmd[cmd.index("--account_pool") + 1] == "true"
    assert "--resume" not in CrawlerManager()._build_command(CrawlerStartRequest(platform=PlatformEnum.XHS))
