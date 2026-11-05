# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
import re
import time
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

PLATFORMS = ("xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu")


class AccountStatus(str, Enum):
    NORMAL = "normal"      # usable (unless cooling down)
    INVALID = "invalid"    # failed too often / cookie expired; needs a new cookie
    DISABLED = "disabled"  # turned off by the user


class AccountInfo(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    platform: str
    account_name: str = ""
    cookies: str
    # Fixed proxy for this account, e.g. http://user:pwd@1.2.3.4:8000. Empty = global proxy config.
    proxy: str = ""
    status: AccountStatus = AccountStatus.NORMAL
    fail_count: int = 0
    last_error: str = ""
    last_used_at: float = 0
    cooling_until: float = 0
    remark: str = ""
    created_at: float = Field(default_factory=time.time)

    @field_validator("platform")
    @classmethod
    def _check_platform(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in PLATFORMS:
            raise ValueError(f"platform must be one of {PLATFORMS}, got {v!r}")
        return v

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        # Used in browser profile dir names; keep it filesystem safe and free of '%'.
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", v or ""):
            raise ValueError("id may only contain letters, digits, '_' and '-'")
        return v

    @field_validator("cookies")
    @classmethod
    def _check_cookies(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("cookies must not be empty")
        return v

    @field_validator("proxy")
    @classmethod
    def _check_proxy(cls, v: Optional[str]) -> str:
        v = (v or "").strip()
        if v and not re.match(r"^https?://", v):
            raise ValueError("proxy must start with http:// or https://")
        return v

    def is_available(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return self.status == AccountStatus.NORMAL and self.cooling_until <= now

    def masked(self) -> dict:
        """Dict for display/API: cookie and proxy password hidden."""
        data = self.model_dump(mode="json")
        c = self.cookies
        data["cookies"] = (c[:12] + "..." + c[-6:]) if len(c) > 24 else "***"
        data["proxy"] = re.sub(r"//([^:/@]+):([^@]+)@", r"//\1:***@", self.proxy)
        data["available"] = self.is_available()
        return data
