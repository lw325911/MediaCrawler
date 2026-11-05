# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
Standalone sign service.

    uv run uvicorn sign_service.server:app --host 127.0.0.1 --port 8989

POST /signsrv/v1/{platform}  body: platform payload  ->  {"ok": true, "data": {...}}
GET  /signsrv/health

Payloads:
  xhs:   {"uri": "/api/sns/web/v1/search/notes", "data": {...}, "cookie_str": "...", "method": "POST"}
  dy:    {"url": "https://www.douyin.com/aweme/v1/web/...", "params": "a=1&b=2", "user_agent": "..."}
  zhihu: {"url": "/api/v4/search_v3?...", "cookies": "d_c0=..."}

If SIGN_SRV_TOKEN is set, requests must send header ``Authorization: Bearer <token>``.
"""
import asyncio
import os

from fastapi import FastAPI, Header, HTTPException
from typing import Any, Dict, Optional

from .signers import SIGNERS

app = FastAPI(title="MediaCrawler Sign Service", version="1.0.0")


@app.get("/signsrv/health")
async def health():
    return {"ok": True, "platforms": sorted(SIGNERS)}


@app.post("/signsrv/v1/{platform}")
async def sign(platform: str, payload: Dict[str, Any], authorization: Optional[str] = Header(default=None)):
    token = os.getenv("SIGN_SRV_TOKEN", "")
    if token and authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="unauthorized")
    signer = SIGNERS.get(platform)
    if signer is None:
        raise HTTPException(status_code=404, detail=f"unsupported platform {platform}")
    try:
        # Signers are CPU / node-subprocess bound; keep the event loop free.
        data = await asyncio.to_thread(signer, payload)
    except KeyError as e:
        return {"ok": False, "error": f"missing field {e}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "data": data}
