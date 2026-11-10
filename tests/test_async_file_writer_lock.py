# -*- coding: utf-8 -*-
import asyncio
import json

import config
from tools.async_file_writer import AsyncFileWriter


def test_concurrent_json_writes_from_separate_writers_keep_all_items(tmp_path, monkeypatch):
    """Stores create a new writer per item; the file lock must still be shared."""
    monkeypatch.setattr(config, "SAVE_DATA_PATH", str(tmp_path))

    async def run():
        await asyncio.gather(*[
            AsyncFileWriter(platform="xhs", crawler_type="search")
            .write_single_item_to_json({"i": i}, "comments")
            for i in range(50)
        ])

    asyncio.run(run())
    files = list((tmp_path / "xhs" / "json").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert sorted(item["i"] for item in data) == list(range(50))
