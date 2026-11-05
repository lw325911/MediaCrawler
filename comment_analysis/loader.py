# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""Load crawled comments from the jsonl / json / csv files MediaCrawler writes."""
import csv
import glob
import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

POST_ID_KEYS = ("note_id", "aweme_id", "video_id", "content_id", "photo_id", "post_id")


@dataclass
class Comment:
    id: str
    post_id: str
    content: str
    like_count: int = 0
    source_keyword: str = ""


def _int(v) -> int:
    try:
        return int(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0


def _to_comment(row: Dict, index: int) -> Optional[Comment]:
    content = (row.get("content") or "").strip()
    if not content:
        return None
    post_id = next((str(row[k]) for k in POST_ID_KEYS if row.get(k)), "")
    return Comment(
        id=str(row.get("comment_id") or row.get("id") or index),
        post_id=post_id,
        content=content,
        like_count=_int(row.get("like_count") or row.get("digg_count")),
        source_keyword=str(row.get("source_keyword") or ""),
    )


def _read_file(path: str) -> Iterable[Dict]:
    if path.endswith(".jsonl"):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue
    elif path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        yield from (data if isinstance(data, list) else [])
    elif path.endswith(".csv"):
        with open(path, encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)


def find_comment_files(platform: str, base_dir: str = "data") -> List[str]:
    files = []
    for ext in ("jsonl", "json", "csv"):
        files += glob.glob(os.path.join(base_dir, platform, ext, f"*comments*.{ext}"))
    return sorted(files)


def load_comments(paths: Iterable[str], keyword: str = "", post_id: str = "") -> List[Comment]:
    seen = set()
    result = []
    n = 0
    for path in paths:
        for row in _read_file(path):
            n += 1
            c = _to_comment(row, n)
            if c is None or (keyword and c.source_keyword != keyword) or (post_id and c.post_id != post_id):
                continue
            key = (c.post_id, c.id, c.content)
            if key in seen:
                continue
            seen.add(key)
            result.append(c)
    return result
