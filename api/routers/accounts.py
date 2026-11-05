# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""Account pool management API (/api/accounts). Cookies are never returned in full."""
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import config
from account_pool import AccountInfo, AccountStore

router = APIRouter(prefix="/accounts", tags=["accounts"])

MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _store() -> AccountStore:
    return AccountStore(config.ACCOUNT_POOL_FILE)


class AccountCreate(BaseModel):
    platform: str
    cookies: str
    account_name: str = ""
    proxy: str = ""
    remark: str = ""


class AccountUpdate(BaseModel):
    cookies: Optional[str] = None
    account_name: Optional[str] = None
    proxy: Optional[str] = None
    remark: Optional[str] = None
    status: Optional[str] = None  # normal | disabled


@router.get("")
async def list_accounts(platform: Optional[str] = None):
    return {"accounts": [a.masked() for a in _store().list(platform)]}


@router.post("")
async def create_account(body: AccountCreate):
    try:
        acc = AccountInfo(**body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if _store().add_many([acc]) == 0:
        raise HTTPException(status_code=409, detail="相同平台和 cookie 的账号已存在")
    return acc.masked()


@router.patch("/{account_id}")
async def update_account(account_id: str, body: AccountUpdate):
    store = _store()
    acc = store.get(account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if "status" in changes and changes["status"] not in ("normal", "disabled"):
        raise HTTPException(status_code=400, detail="status 只能是 normal 或 disabled")
    try:
        updated = AccountInfo(**{**acc.model_dump(), **changes})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if "cookies" in changes:  # new cookie: give the account a clean slate
        updated.fail_count, updated.cooling_until, updated.last_error = 0, 0, ""
        updated.status = updated.status if "status" in changes else "normal"
    return store.upsert(updated).masked()


@router.post("/{account_id}/reset")
async def reset_account(account_id: str):
    acc = _store().reset(account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return acc.masked()


@router.delete("/{account_id}")
async def delete_account(account_id: str):
    if not _store().remove(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"deleted": account_id}


@router.post("/import")
async def import_accounts(request: Request, filename: str):
    """Upload the raw file as the request body: POST /api/accounts/import?filename=accounts.xlsx"""
    suffix = os.path.splitext(filename or "")[1].lower()
    if suffix not in (".csv", ".xlsx", ".json"):
        raise HTTPException(status_code=400, detail="只支持 .csv / .xlsx / .json")
    content = b""
    async for chunk in request.stream():
        content += chunk
        if len(content) > MAX_IMPORT_BYTES:
            raise HTTPException(status_code=400, detail="文件太大（上限 5MB）")
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        try:
            accounts = AccountStore.read_import_file(tmp)
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:  # malformed csv/xlsx/json
            raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")
    finally:
        os.unlink(tmp)
    added = _store().add_many(accounts)
    return {"read": len(accounts), "added": added}
