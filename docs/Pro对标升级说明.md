# 对标 Pro 版的升级功能说明

本分支参考 MediaCrawlerPro 公开的功能列表，自行实现了以下能力（未参考 Pro 源码）。

| 功能 | 用法 | 支持范围 |
| --- | --- | --- |
| 断点续爬 | 默认开启；中断后用相同参数重跑即可继续。关闭：`--resume false` | xhs、dy 的 search / detail / creator |
| 多账号池 | `python -m account_pool add/import/list/reset/remove`；运行加 `--account_pool true` | 全部平台（cookie 登录） |
| 账号绑定代理 | 账号的 `proxy` 字段，填写后该账号固定走这个代理 | 全部平台 |
| Docker 部署 | `docker compose up -d`，WebUI 在 http://localhost:8080 | Linux / 服务器 |
| 环境变量配置 | 任何配置项都可以用 `MC_<配置名>` 覆盖，例如 `MC_SAVE_DATA_OPTION=db` | 全部 |
| 无界面扫码 | 二维码同时保存到 `data/login_qrcode.png` | 全部 |
| 签名服务 | `uvicorn sign_service.server:app --port 8989`，再设置 `MC_SIGN_SRV_URL=http://127.0.0.1:8989` | xhs、dy、zhihu |
| 热搜榜单 | `python -m hot_search --platform dy|bili|wb|zhihu` | wb、zhihu 需要登录 cookie |
| AI 评论分析 | `uv pip install anthropic` 后 `python -m comment_analysis --platform xhs --keyword 关键词` | 读取已爬取的评论文件 |
| 任务队列 | WebUI 接口 `POST /api/crawler/queue`、`GET/DELETE /api/crawler/queue` | WebUI |
| Cookie 同步扩展 | Chrome 打开 `chrome://extensions` → 开发者模式 → 加载 `tools/cookie_bridge_extension` | 需要 WebUI 在运行 |
| Agent Skill | 把 `skills/mediacrawler` 复制到 `~/.claude/skills/` | Claude Code 等 |

## 账号池

```shell
# 单个添加
uv run python -m account_pool add --platform xhs --cookies "a1=...; web_session=..." --name 小号1 --proxy http://user:pwd@1.2.3.4:8000
# 批量导入（csv / xlsx / json，列：platform, account_name, cookies, proxy, remark）
uv run python -m account_pool import accounts.xlsx
# 查看状态
uv run python -m account_pool list --platform xhs
# 使用账号池爬取
uv run main.py --platform xhs --type search --keywords 编程副业 --account_pool true
```

规则：每次挑最久没用过的可用账号；账号报错、被风控或任务中途停止时，该账号冷却 `600 × 2^(n-1)` 秒并切换下一个账号继续（xhs、dy 从断点继续）；连续失败 3 次标记为失效，更新 cookie 或执行 `reset` 后恢复。账号池模式下每个账号使用独立浏览器目录，并且不使用 CDP 模式（避免覆盖你自己 Chrome 里的登录）。相关配置见 `config/base_config.py` 中 `ACCOUNT_*`。

## Docker

```shell
docker compose up -d                                   # WebUI + API
docker compose --profile mysql up -d                   # 同时启动 MySQL，配合 MC_SAVE_DATA_OPTION=db
docker compose --profile sign up -d                    # 同时启动签名服务
docker compose run --rm crawler --platform xhs --lt cookie --cookies "..." --type search --keywords 编程
```

容器默认无界面运行（`MC_ENABLE_CDP_MODE=false`、`MC_HEADLESS=true`），数据在 `./data`，浏览器登录态在 `./browser_data`。扫码登录时打开 `./data/login_qrcode.png` 扫码，或者直接用 cookie / 账号池登录。

## 已知限制

- 断点续爬目前只接入了小红书和抖音；其他平台中断后会从头开始。
- 快手、B 站、微博、贴吧的签名仍依赖浏览器环境，不走签名服务，所以还不能完全去掉 Playwright。
- 微博、知乎热搜和 AI 评论分析没有在真实账号/API key 下实测，需要测试同学重点验证。
