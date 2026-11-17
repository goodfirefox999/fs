"""HTTP 层：GB18030 解码 + 全局令牌桶（≥2.0s）+ 指数退避重试 + 连续 5xx 暂停告警。

规格依据（工作指令 §2.1）：
- 全局请求速率 ≤ 0.5 req/s（任意两次 HTTP 请求间隔 ≥ 2.0 秒），令牌桶，全站共享
- 单页重试最多 3 次，指数退避 5s/15s/45s，±20% 随机抖动
- 连续 5 次 5xx/超时 → 暂停 10 分钟并写告警日志
- 固定单一真实 UA
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from .config import HttpConfig, RateLimitConfig

log = logging.getLogger("collector.http")

UA_FALLBACK = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"


class TokenBucket:
    """全站共享的限速桶：保证任意两次 acquire() 间隔 ≥ min_interval 秒。"""

    def __init__(self, min_interval: float, jitter_ratio: float = 0.0) -> None:
        if min_interval <= 0:
            raise ValueError("min_interval 必须 > 0")
        self._min_interval = min_interval
        self._jitter = max(0.0, jitter_ratio)
        self._lock = threading.Lock()
        self._last: float | None = None

    def acquire(self, sleeper: Callable[[float], None] = time.sleep) -> float:
        """阻塞至可发请求；返回本次等待秒数（便于测试注入时钟）。"""
        with self._lock:
            now = time.monotonic()
            if self._last is None:
                self._last = now          # 首次调用不等待
                return 0.0
            wait = self._min_interval - (now - self._last)
            if wait > 0:
                jitter = random.uniform(-self._jitter, self._jitter) * self._min_interval
                wait += max(0.0, jitter)
                sleeper(wait)
                waited = wait
            else:
                waited = 0.0
            self._last = time.monotonic()
            return waited


class SharedTokenBucket:
    """跨进程共享令牌桶：flock 预约槽位 + 墙钟时间戳文件。

    锁内只做「预约下一个可用时刻」（原子读改写），睡眠在锁外进行——
    避免一个进程持锁睡眠导致另一个进程饥饿。
    全局保证任意两次请求（跨所有进程）间隔 ≥ min_interval。
    时间戳用 time.time()（墙钟），time.monotonic() 跨进程不可比。
    """

    def __init__(self, path: Path, min_interval: float, jitter_ratio: float = 0.0) -> None:
        import fcntl  # noqa: PLC0415 - POSIX 限定，项目运行环境为 macOS/Linux

        self._fcntl = fcntl
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("0.0\n")
        self._min_interval = min_interval
        self._jitter = max(0.0, jitter_ratio)

    def acquire(self, sleeper: Callable[[float], None] = time.sleep) -> float:
        with open(self._path, "r+") as f:
            self._fcntl.flock(f.fileno(), self._fcntl.LOCK_EX)
            try:
                raw = f.read().strip() or "0.0"
                last = float(raw)
                now = time.time()
                start = max(now, last + self._min_interval)
                if start > now and self._jitter > 0:
                    start += random.uniform(0.0, self._jitter) * self._min_interval
                f.seek(0)
                f.write(f"{start}\n")
                f.truncate()
                wait = start - now
            finally:
                self._fcntl.flock(f.fileno(), self._fcntl.LOCK_UN)
        if wait > 0:
            sleeper(wait)
            return wait
        return 0.0


@dataclass
class FetchResult:
    url: str
    status: int
    body: bytes
    elapsed: float
    attempts: int


@dataclass
class HttpMetrics:
    total_requests: int = 0
    total_retries: int = 0
    total_elapsed: float = 0.0
    consecutive_server_errors: int = 0
    pause_count: int = 0
    request_log: list[dict[str, object]] = field(default_factory=list)

    def record(self, url: str, status: int, elapsed: float, attempts: int) -> None:
        self.total_requests += 1
        self.total_retries += attempts - 1
        self.total_elapsed += elapsed
        self.request_log.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "url": url,
                "status": status,
                "elapsed_s": round(elapsed, 3),
                "attempts": attempts,
            }
        )

    def summary(self) -> dict[str, object]:
        n = max(1, self.total_requests)
        return {
            "total_requests": self.total_requests,
            "total_retries": self.total_retries,
            "total_elapsed_s": round(self.total_elapsed, 1),
            "avg_interval_s": round(self.total_elapsed / n, 3),
            "pause_count": self.pause_count,
        }


class AlertLogger:
    """告警日志：logs/alerts.log（JSON lines）。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, kind: str, message: str, **extra: object) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            "message": message,
            **extra,
        }
        with self._lock, open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class BrowserSession:
    """同步 HTTP 会话：令牌桶 + GB18030 解码 + 重试 + 连续失败暂停。"""

    def __init__(
        self,
        http_cfg: HttpConfig,
        rate_cfg: RateLimitConfig,
        alerts: AlertLogger,
        metrics: HttpMetrics | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        verify: str | bool = http_cfg.ca_bundle or True
        self._client = httpx.Client(
            headers={"User-Agent": http_cfg.user_agent or UA_FALLBACK},
            timeout=httpx.Timeout(http_cfg.timeout_seconds),
            verify=verify,
            follow_redirects=True,
        )
        shared = getattr(rate_cfg, "shared_bucket_file", None)
        if shared:
            self._bucket: TokenBucket | SharedTokenBucket = SharedTokenBucket(
                Path(shared), rate_cfg.min_interval_seconds, rate_cfg.jitter_ratio
            )
        else:
            self._bucket = TokenBucket(rate_cfg.min_interval_seconds, rate_cfg.jitter_ratio)
        self._rate = rate_cfg
        self._alerts = alerts
        self.metrics = metrics if metrics is not None else HttpMetrics()
        self._sleeper = sleeper

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BrowserSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_bytes(self, url: str) -> FetchResult:
        """GET 原始字节，带重试与连续 5xx 暂停。"""
        attempts = 0
        start_all = time.monotonic()
        while True:
            attempts += 1
            self._bucket.acquire(self._sleeper)
            t0 = time.monotonic()
            status, body, err = self._once(url)
            elapsed = time.monotonic() - t0
            self.metrics.record(url, status, elapsed, attempts)
            log.info("GET %s -> %s (%.2fs, attempt %d)", url, status, elapsed, attempts)
            if status == 200:
                self.metrics.consecutive_server_errors = 0
                return FetchResult(url, 200, body, time.monotonic() - start_all, attempts)
            is_server_side = status >= 500 or status == 0
            if not is_server_side:
                # 4xx：不重试（本站无权限墙；404 即目标异常）
                raise RuntimeError(f"HTTP {status} for {url}")
            self.metrics.consecutive_server_errors += 1
            if self.metrics.consecutive_server_errors >= self._rate.consecutive_5xx_pause_threshold:
                self.metrics.consecutive_server_errors = 0
                self.metrics.pause_count += 1
                self._alerts.write(
                    "PAUSE_5XX",
                    f"连续 {self._rate.consecutive_5xx_pause_threshold} 次 5xx/超时，暂停 {self._rate.pause_seconds}s",
                    url=url,
                )
                log.warning("连续 5xx，暂停 %ds", self._rate.pause_seconds)
                self._sleeper(self._rate.pause_seconds)
            if attempts >= self._rate.retry_attempts:
                self.metrics.consecutive_server_errors = 0
                raise RuntimeError(f"HTTP {status} for {url} after {attempts} attempts")
            backoff = self._rate.retry_backoff_seconds[min(attempts - 1, len(self._rate.retry_backoff_seconds) - 1)]
            backoff *= random.uniform(0.8, 1.2)  # ±20% 抖动
            self._sleeper(backoff)
            start_all = time.monotonic()

    def _once(self, url: str) -> tuple[int, bytes, str | None]:
        try:
            resp = self._client.get(url)
            return resp.status_code, resp.content, None
        except httpx.HTTPError as exc:
            return 0, b"", str(exc)

    def wait_turn(self) -> None:
        """按全局令牌桶等待本轮请求时机（供轻量抓取路径使用）。"""
        self._bucket.acquire()

    def get_text(self, url: str) -> FetchResult:
        """GET 并按 GB18030 解码（文档实测：本站编码为 GB18030）。"""
        result = self.get_bytes(url)
        return result


def decode_gb18030(body: bytes) -> str:
    """站点编码 GB18030；先查 meta 声明再解码，异常字符用替换符保底。"""
    head = body[:2048].lower()
    if b"charset=utf-8" in head:
        return body.decode("utf-8", errors="replace")
    return body.decode("gb18030", errors="replace")


def extract_title(html_text: str) -> str:
    i = html_text.find("<title>")
    if i < 0:
        return ""
    j = html_text.find("</title>", i)
    return html_text[i + len("<title>") : j].strip() if j > 0 else ""


def is_valid_thread(html_text: str) -> bool:
    """无效 tid 返回 HTTP 200，必须用内容判定（文档 §T2）。"""
    title = extract_title(html_text)
    if "帖子ID非法" in title:
        return False
    if "没有权限" in html_text:
        return False
    if "tpc_content" not in html_text:
        return False
    return True
