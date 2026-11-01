"""CI 门禁：``status`` 字段变更必须带人类签名（commit trailer ``Verified-By:``）。

规则（docs/DEVELOPMENT.md 第 5.3 节）
------------------------------------
- Agent 只能创建 ``draft`` / ``待考证``；
- 把状态改为 ``已考证`` / ``有争议`` / ``弃用`` 的提交必须由人类签名；
- 判定方式：``git diff`` 中若 ``status:`` 行的值进入 HUMAN_ONLY_TARGETS，
  则该提交的 commit message 必须含 ``Verified-By: <人名>``。

用法
----
``python3 tools/check_status_signature.py [--base origin/main] [--head HEAD]``
无 git 环境（如打包分发）时以 ``--offline`` 跳过并返回 0。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HUMAN_ONLY = {"已考证", "有争议", "弃用"}
STATUS_RE = re.compile(r"^\s*status:\s*(\S+)\s*$")
SIGN_RE = re.compile(r"^\s*Verified-By:\s*(\S.*)$", re.MULTILINE)


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _changed_rule_files(base: str, head: str, root: Path) -> list[str]:
    out = _git("diff", "--name-only", base, head, cwd=root)
    return [line for line in out.splitlines() if line.startswith("core-rule/rules/") and line.endswith(".yaml")]


def _status_changes(base: str, head: str, path: str, root: Path) -> set[str]:
    diff = _git("diff", "-U0", base, head, "--", path, cwd=root)
    added: set[str] = set()
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            m = STATUS_RE.match(line[1:])
            if m:
                added.add(m.group(1))
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--offline", action="store_true", help="无 git 环境时跳过检查")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)

    root = Path(args.root)
    if args.offline:
        print("⚠️  离线模式：跳过 status 签名检查（发布前必须在线校验）")
        return 0

    try:
        message = _git("log", "-1", "--format=%B", args.head, cwd=root)
        files = _changed_rule_files(args.base, args.head, root)
    except subprocess.CalledProcessError as exc:
        print(f"⚠️  git 调用失败（{exc}）；请确认 base 分支存在，或使用 --offline")
        return 0

    offenders: list[tuple[str, set[str]]] = []
    for path in files:
        touched = _status_changes(args.base, args.head, path, root) & HUMAN_ONLY
        if touched:
            offenders.append((path, touched))

    if not offenders:
        print("✅ status 签名检查通过（无人类专属状态变更）")
        return 0

    if SIGN_RE.search(message):
        signer = SIGN_RE.search(message).group(1)  # type: ignore[union-attr]
        print(f"✅ status 变更已由人类签名：{signer}")
        for path, touched in offenders:
            print(f"   - {path}: {sorted(touched)}")
        return 0

    print("❌ 检测到人类专属状态变更但缺少签名：")
    for path, touched in offenders:
        print(f"   - {path}: {sorted(touched)}")
    print("\n修复：在 commit message 中加入 `Verified-By: <考证者姓名>`。")
    print("依据：docs/DEVELOPMENT.md 第 5.3 节（Agent 不得自行把规则标为已考证）。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
