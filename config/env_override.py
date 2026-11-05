# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
Override config values from environment variables (handy for Docker / servers).

Any upper-case config name can be set as ``MC_<NAME>``, e.g.::

    MC_ENABLE_CDP_MODE=false MC_HEADLESS=true MC_SAVE_DATA_OPTION=db

The value is converted to the type of the existing default:
bool -> true/false/1/0/yes/no, int, float, list/dict -> JSON, otherwise str.
Command line arguments are applied later and still win.
"""

import json
import os
from typing import Any, Dict

ENV_PREFIX = "MC_"
_TRUE = {"1", "true", "t", "yes", "y", "on"}
_FALSE = {"0", "false", "f", "no", "n", "off", ""}


def _convert(raw: str, default: Any) -> Any:
    if isinstance(default, bool):
        value = raw.strip().lower()
        if value in _TRUE:
            return True
        if value in _FALSE:
            return False
        raise ValueError(f"not a boolean: {raw!r}")
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    if isinstance(default, (list, dict)):
        value = json.loads(raw)
        if not isinstance(value, type(default)):
            raise ValueError(f"expected JSON {type(default).__name__}")
        return value
    return raw


def apply_env_overrides(namespace: Dict[str, Any], environ=None) -> Dict[str, Any]:
    """Apply MC_* variables onto ``namespace`` in place; returns what changed."""
    environ = os.environ if environ is None else environ
    applied = {}
    for env_key, raw in environ.items():
        if not env_key.startswith(ENV_PREFIX):
            continue
        name = env_key[len(ENV_PREFIX):]
        if not name.isupper() or name not in namespace or callable(namespace[name]):
            continue
        try:
            namespace[name] = _convert(raw, namespace[name])
        except (ValueError, TypeError) as e:
            raise ValueError(f"环境变量 {env_key} 的值无效: {e}") from e
        applied[name] = namespace[name]
    return applied
