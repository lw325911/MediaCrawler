# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。

"""
Checkpoint / resume support for crawler tasks (断点续爬).

A checkpoint records what a task has already finished, so an interrupted
run (Ctrl+C, crash, risk-control block) can be restarted and skip that work.

* A task is identified by platform + crawler type + its inputs (keywords,
  id lists, sort options...). Changing the inputs starts a fresh checkpoint.
* Progress is kept per "scope" (a keyword, a creator, or "detail"):
  finished pages, finished item ids, and whether the scope is fully done.
* Every change is written to disk immediately with an atomic replace, so the
  file is consistent even if the process is killed mid-run.
* When the whole task completes, the checkpoint file is deleted. A later
  run with the same inputs therefore crawls fresh data again; only an
  interrupted run leaves a checkpoint behind.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import config
from tools import utils


class CrawlerCheckpoint:
    VERSION = 1

    def __init__(self, platform: str, crawler_type: str, task_inputs: Dict[str, Any],
                 checkpoint_dir: Optional[str] = None, enabled: bool = True):
        self.platform = platform
        self.crawler_type = crawler_type
        self.enabled = enabled
        self.task_key = self.build_task_key(platform, crawler_type, task_inputs)
        base_dir = checkpoint_dir or getattr(config, "CHECKPOINT_DIR", "") or "data/checkpoints"
        self.path = Path(base_dir) / f"{platform}_{crawler_type}_{self.task_key}.json"
        self._state: Dict[str, Any] = self._empty_state(task_inputs)
        self.resumed = False
        if self.enabled:
            self._load()

    # ------------------------------------------------------------------ #
    # identity / persistence
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_task_key(platform: str, crawler_type: str, task_inputs: Dict[str, Any]) -> str:
        raw = json.dumps(
            {"platform": platform, "crawler_type": crawler_type, "inputs": task_inputs},
            sort_keys=True, ensure_ascii=False, default=str,
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def _empty_state(self, task_inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "platform": self.platform,
            "crawler_type": self.crawler_type,
            "task_inputs": task_inputs,
            "scopes": {},
        }

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            utils.logger.warning(f"[CrawlerCheckpoint] 断点文件损坏，忽略并重新开始: {self.path}, err: {e}")
            return
        if data.get("version") != self.VERSION:
            utils.logger.warning(f"[CrawlerCheckpoint] 断点文件版本不匹配，忽略: {self.path}")
            return
        self._state = data
        self.resumed = True
        utils.logger.info(f"[CrawlerCheckpoint] 发现断点，将从上次进度继续: {self.path} ({self.summary()})")

    def _save(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".ckpt_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _scope(self, scope: str) -> Dict[str, Any]:
        scopes = self._state["scopes"]
        if scope not in scopes:
            scopes[scope] = {"pages": [], "items": [], "done": False}
        return scopes[scope]

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def is_scope_done(self, scope: str) -> bool:
        return self.enabled and self._state["scopes"].get(scope, {}).get("done", False)

    def mark_scope_done(self, scope: str) -> None:
        if not self.enabled:
            return
        self._scope(scope)["done"] = True
        self._save()

    def is_page_done(self, scope: str, page: int) -> bool:
        return self.enabled and page in self._state["scopes"].get(scope, {}).get("pages", [])

    def mark_page_done(self, scope: str, page: int) -> None:
        if not self.enabled:
            return
        pages = self._scope(scope)["pages"]
        if page not in pages:
            pages.append(page)
            self._save()

    def is_item_done(self, scope: str, item_id: str) -> bool:
        return self.enabled and str(item_id) in self._state["scopes"].get(scope, {}).get("items", [])

    def filter_pending(self, scope: str, item_ids: Iterable[str]) -> List[str]:
        """Return the ids not finished yet, keeping order."""
        return [i for i in item_ids if not self.is_item_done(scope, i)]

    def mark_items_done(self, scope: str, item_ids: Iterable[str]) -> None:
        if not self.enabled:
            return
        items = self._scope(scope)["items"]
        known = set(items)
        changed = False
        for item_id in item_ids:
            if item_id and str(item_id) not in known:
                items.append(str(item_id))
                known.add(str(item_id))
                changed = True
        if changed:
            self._save()

    def finish(self) -> None:
        """Whole task completed: remove the checkpoint file."""
        if not self.enabled:
            return
        try:
            self.path.unlink()
            utils.logger.info(f"[CrawlerCheckpoint] 任务完成，已清理断点文件: {self.path}")
        except FileNotFoundError:
            pass

    def summary(self) -> str:
        scopes = self._state["scopes"]
        done = sum(1 for s in scopes.values() if s.get("done"))
        items = sum(len(s.get("items", [])) for s in scopes.values())
        return f"已完成范围 {done}/{len(scopes)}，已完成条目 {items}"


def create_checkpoint(platform: str, crawler_type: str, task_inputs: Dict[str, Any]) -> CrawlerCheckpoint:
    """Build a checkpoint honoring config.ENABLE_CHECKPOINT."""
    return CrawlerCheckpoint(
        platform=platform,
        crawler_type=crawler_type,
        task_inputs=task_inputs,
        enabled=getattr(config, "ENABLE_CHECKPOINT", False),
    )
