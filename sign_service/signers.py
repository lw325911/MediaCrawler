# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""In-process signers. Each takes a JSON-able payload dict and returns a dict of sign values."""
from typing import Any, Callable, Dict


def sign_xhs(payload: Dict[str, Any]) -> Dict[str, str]:
    from media_platform.xhs.playwright_sign import _sign_with_xhshow_local

    return _sign_with_xhshow_local(
        uri=payload["uri"],
        data=payload.get("data"),
        cookie_str=payload.get("cookie_str", ""),
        method=payload.get("method", "POST"),
    )


def sign_dy(payload: Dict[str, Any]) -> Dict[str, str]:
    from media_platform.douyin.help import _get_a_bogus_local

    return {"a_bogus": _get_a_bogus_local(payload["url"], payload["params"], payload["user_agent"])}


def sign_zhihu(payload: Dict[str, Any]) -> Dict[str, str]:
    from media_platform.zhihu.help import _zhihu_sign_local

    return _zhihu_sign_local(payload["url"], payload.get("cookies", ""))


SIGNERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, str]]] = {
    "xhs": sign_xhs,
    "dy": sign_dy,
    "zhihu": sign_zhihu,
}
