# fengshui-collector

堪舆案例语料采集与结构化流水线（个人研究用）。采集两个论坛：

| 线 | 站点 | 程序 | 数据库 |
|---|---|---|---|
| 龙坛 | 龙行天下风水论坛 `ok2009ok.com` | PHPWind 7.x / GB18030 | `data/fs.sqlite` |
| fs168 | 天機易學論壇 `fengshui-168.com` | Discuz! X3 | `data/fs168/fs168.sqlite` |

> 产出为结构化观测数据，不构成任何吉凶判定结论。原文原图版权归原作者所有；
> 个人研究用途，不公开分发、不再传播。`data/`（约 25GB）不进版本控制。

## 安装

需要 Python 3.11+（锁文件在 3.14 上生成）。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock     # 换机器 / CI 一律装锁文件
```

- `requirements.txt` / `requirements-dev.txt`：运行时与开发期的**声明**（只写下限）
- `requirements.lock`：`pip freeze` 出的**精确版本**，可复现的唯一依据
- 改了依赖后重新生成：`.venv/bin/pip freeze > requirements.lock`，并确认声明项都在 lock 里

```bash
.venv/bin/python -m pytest -q                   # 测试
.venv/bin/python -m mypy src                    # 静态检查（strict）
```

## 龙坛线

```bash
.venv/bin/python -m src.pipeline --help
# 子命令：discover discover_digest crawl reparse images marks bearings report verify
# 全部支持断点续跑；原始 HTML 以 gzip 归档在 data/raw/，之后可离线重解析。
```

- `reparse` / `bearings` 只读已归档的 HTML，**不产生任何网络请求**——源站不可用时仍可推进
- 图片下载与标注分割受授权门控（配置项 `image_download_approved`），默认不下载
- 限速：进程内令牌桶 + 跨进程共享令牌桶（`data/.rate_bucket`），多进程并发时同样生效

## fs168 线

```bash
bash scripts/fs168_full_chain.sh                # 图片补下 → 深采 → 缺口回填 → 核对 → 再补一轮
.venv/bin/python scrapers/fs168_clean.py        # 清洗（全链脚本不含这一步，需单独跑）
.venv/bin/python scrapers/fs168_extract.py      # 结构化抽取（方位 / 段落）
```

- 站点有 Cloudflare 质询：会话 cookie 存在 `data/fs168/session.json`（不进版本控制）
- 所有 HTTP 请求统一走 `fs168_digest.fetch()`，限速在这一处生效

## 复核与导出

```bash
.venv/bin/python tools/review_queue.py          # 导出 needs_review 复核清单（两库幂等加复核列）
```
