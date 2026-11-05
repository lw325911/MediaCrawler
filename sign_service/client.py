# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""Client side: decide between in-process signing and the remote sign service."""
from typing import Any, Dict

import httpx

import config


class SignServiceError(RuntimeError):
    pass


def remote_enabled() -> bool:
    return bool(getattr(config, "SIGN_SRV_URL", ""))


def remote_sign(platform: str, payload: Dict[str, Any]) -> Dict[str, str]:
    base = config.SIGN_SRV_URL.rstrip("/")
    timeout = float(getattr(config, "SIGN_SRV_TIMEOUT", 10))
    try:
        token = getattr(config, "SIGN_SRV_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = httpx.post(f"{base}/signsrv/v1/{platform}", json=payload, headers=headers,
                          timeout=timeout, trust_env=False)
    except httpx.HTTPError as e:
        raise SignServiceError(f"签名服务不可用 ({base}): {e}") from e
    if resp.status_code != 200:
        raise SignServiceError(f"签名服务返回 {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    if not body.get("ok"):
        raise SignServiceError(f"签名失败: {body.get('error')}")
    return body["data"]
