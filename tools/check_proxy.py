#!/usr/bin/env python3
"""push 前代理预检：把「环境变量丢了」和「上游断了」分开。

背景（2026-11-03 评审七回路）
----------------------------
本仓库的 git 曾没有设置 ``http.proxy``/``https.proxy``，完全依赖环境变量
``https_proxy=127.0.0.1:62727``；后续环境里该变量也可能不存在。这带来一个
取证难点：push 失败时，

- 上游 502 → 代理进程活着、环境变量也在；
- 子进程丢失环境变量 → 代理进程也活着，但请求根本没走代理。

两者在终端上都表现为「超时」，只看 git 报错无法区分。本工具把判据固定为：

1. 代理从哪来（环境变量 / git config）；
2. 经代理能不能到目标 URL；
3. 代理失败时，直连能不能到——能，则问题在代理/环境变量；不能，才可能是上游。

输出固定三行，避免「预检说 200，push 却走了另一条路失败」::

    env_proxy: 有（https_proxy=...）  git_config_proxy: 无
    direct: 200  via_proxy: 200
    push_route: 当前将走 proxy（环境变量 https_proxy）

用法::

    python tools/check_proxy.py
    python tools/check_proxy.py --url https://github.com --timeout 10

退出码：0 = 可达（含「未配置代理但直连可达」）；1 = 不可达；2 = 工具本身无法执行检查。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

__all__ = ["check", "env_proxy", "git_proxy", "probe", "safe_proxy"]

_ENV_KEYS = ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY")
_GIT_KEYS = ("https.proxy", "http.proxy")


def safe_proxy(value: str) -> str:
    """隐藏代理 URL 里的 user:pass，避免把凭据写进日志。"""
    if "@" not in value:
        return value
    scheme, _, rest = value.partition("://")
    if not rest:
        return "***"
    return f"{scheme}://***@{rest.rsplit('@', 1)[-1]}"


def env_proxy(env: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    """返回 (变量名, 值)；https_proxy 优先于 http_proxy。"""
    source = env if env is not None else os.environ
    for key in _ENV_KEYS:
        value = source.get(key)
        if value:
            return key, value
    return None, None


def git_proxy() -> tuple[str | None, str | None]:
    """读取 git 的显式代理配置（本地/全局都算）。"""
    for key in _GIT_KEYS:
        try:
            proc = subprocess.run(
                ["git", "config", "--get", key],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        value = proc.stdout.strip()
        if proc.returncode == 0 and value:
            return key, value
    return None, None


def probe(url: str, *, proxy: str | None = None, timeout: int = 10) -> tuple[bool, str]:
    """用 curl 探一次目标 URL；返回 (是否可达, 证据)。"""
    cmd = [
        "curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
        "--max-time", str(timeout),
    ]
    if proxy:
        cmd.extend(["-x", proxy])
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        return False, "curl 超时"
    except OSError as exc:
        return False, f"curl 不可用：{exc}"
    code = proc.stdout.strip()
    if proc.returncode != 0:
        # 超时/连接重置时 curl 可能已打印部分 HTTP 码（甚至 200），必须带 rc，
        # 否则会报出「direct: 200」却判失败，读日志的人无法理解。
        detail = code if code and code != "000" else (proc.stderr.strip() or "无输出")
        return False, f"{detail} (curl rc={proc.returncode})"
    ok = code[:1] in {"2", "3"}
    return ok, code or (proc.stderr.strip() or f"curl rc={proc.returncode}")


def check(url: str, *, timeout: int = 10) -> int:
    """打印环境/代理/直连三条证据，再按「push 实际会走的路」判定。"""
    env_key, env_value = env_proxy()
    git_key, git_value = git_proxy()

    # 先报来源：两次结论对不上时，第一眼就能看到是环境变量变了还是 git config 变了。
    env_desc = f"有（{env_key}={safe_proxy(env_value)}）" if env_value else "无"
    git_desc = f"有（{git_key}={safe_proxy(git_value)}）" if git_value else "无"
    print(f"env_proxy: {env_desc}  git_config_proxy: {git_desc}")

    # 直连永远探一次，作为对照；代理配置则再探一次。两条路都留下证据，
    # 避免「预检说 200，push 却走了另一条路失败」时无法定位。
    direct_ok, direct_evidence = probe(url, timeout=timeout)
    if env_value or git_value:
        proxy_value = env_value or git_value
        via_ok, via_evidence = probe(url, proxy=proxy_value, timeout=timeout)
    else:
        proxy_value = None
        via_ok, via_evidence = False, "未配置"
    print(f"direct: {direct_evidence}  via_proxy: {via_evidence}")

    # push 实际会走哪条：环境变量优先（git 子进程默认继承），否则 git config，最后直连。
    if env_value:
        route = f"proxy（环境变量 {env_key}）"
    elif git_value:
        route = f"proxy（git config {git_key}）"
    else:
        route = "direct"
    print(f"push_route: 当前将走 {route}")

    if proxy_value:
        if via_ok:
            print(f"✅ 经代理可达 {url}（HTTP {via_evidence}）")
            return 0
        print(f"❌ 经代理不可达 {url}（{via_evidence}）")
        if direct_ok:
            print(
                f"⚠️  直连可达（HTTP {direct_evidence}）——问题在代理/环境变量，不是上游。\n"
                "   处置：确认代理进程与端口；若代理已停，可 unset https_proxy 后重试。"
            )
        else:
            print(
                f"❌ 直连也不可达（{direct_evidence}）——更像上游/网络故障，"
                "不是环境变量丢失。稍后重试并记录对照。"
            )
        return 1

    if direct_ok:
        print(
            f"⚠️  未配置代理（环境变量与 git config 都没有），但直连可达 {url}"
            f"（HTTP {direct_evidence}）。\n"
            "   若本机预期走代理，说明当前进程丢了 https_proxy——这不会报错，只会静默直连。"
        )
        return 0
    print(
        f"❌ 未配置代理且直连不可达 {url}（{direct_evidence}）。\n"
        "   先确认 https_proxy 是否应在当前进程环境中；不要直接归因「上游挂了」。"
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="push 前代理预检")
    parser.add_argument("--url", default="https://github.com", help="要探测的 URL")
    parser.add_argument("--timeout", type=int, default=10, help="curl 超时秒数")
    args = parser.parse_args(argv)

    try:
        return check(args.url, timeout=args.timeout)
    except Exception as exc:  # pragma: no cover - 兜底，避免预检把 push 卡死
        print(f"❌ 代理预检自身异常：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
