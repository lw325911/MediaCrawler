---
name: mediacrawler
description: Crawl public posts and comments from Xiaohongshu, Douyin, Kuaishou, Bilibili, Weibo, Tieba or Zhihu with the local MediaCrawler checkout, fetch hot search lists, and analyze comments. Use when the user asks to collect or analyze social media data with MediaCrawler.
---

# MediaCrawler

Run everything from the MediaCrawler repository root with `uv run`. Use it for learning and research only, keep request rates low, and respect each platform's terms.

## 1. Pick the command

| Goal | Command |
| --- | --- |
| Search by keyword | `uv run main.py --platform xhs --type search --keywords "关键词1,关键词2"` |
| Specific posts | `uv run main.py --platform dy --type detail --specified_id "<url or id>,<url or id>"` |
| Creator homepage | `uv run main.py --platform bili --type creator --creator_id "<id>"` |
| Hot search list | `uv run python -m hot_search --platform dy` (dy, bili work without login; wb, zhihu need `--cookies` or `--use-account-pool`) |
| Comment analysis report | `uv run python -m comment_analysis --platform xhs --keyword 关键词` (needs `uv pip install anthropic` and an Anthropic API key; sends comment text to the Claude API, so confirm with the user first) |

Platforms: `xhs` 小红书, `dy` 抖音, `ks` 快手, `bili` B站, `wb` 微博, `tieba` 贴吧, `zhihu` 知乎.

Useful flags: `--get_comment true|false`, `--get_sub_comment true`, `--crawler_max_notes_count 20`, `--max_comments_count_singlenotes 50`, `--save_data_option jsonl|csv|excel|sqlite|db`, `--headless true`, `--get_media true`.

## 2. Login

- If the account pool has accounts for the platform (`uv run python -m account_pool list --platform xhs`), add `--account_pool true`. Failed or blocked accounts are rotated automatically.
- Otherwise ask the user for a cookie string and pass `--lt cookie --cookies "<cookie>"`, or use `--lt qrcode` and tell the user to scan `data/login_qrcode.png`.
- Never print full cookies back to the user.

## 3. Resume

Checkpointing is on by default for xhs and dy (`--resume true`). If a run stops early, rerun the exact same command and it continues where it stopped. A run that finishes deletes its checkpoint.

## 4. Results

Data is written to `data/<platform>/<format>/<type>_{contents|comments|creators}_<date>.<ext>`. Read the newest files there to answer the user's question, and report counts and the file paths you used.
