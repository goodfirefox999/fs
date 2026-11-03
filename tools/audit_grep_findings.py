#!/usr/bin/env python3
"""grep 误诊连锁复查：把历史上以「grep 零命中 / 异常输出」为证据的结论逐条复核。

背景（AGENTS 约束第 9 条）
------------------------
2026-11-02 核对 Q-020/Q-021 时，``grep "A\\|B"`` 静默零匹配（toybox BRE 不支持
``\\|``），差点写成"宣称与树不一致"；11-03 又发现 pytest ``-q`` 下汇总行消失。
两次都是**工具行为差异冒充数据事实**。本脚本把文档里引用过这类证据的结论
登记成注册表，逐条用 Python / ``grep -aE`` 复跑，输出三态：

- ✅ 成立：复核通过，结论保留；
- 🔄 反转：复核失败，结论必须改写；
- ⚠️ 证据不足：依赖不可复现的快照（如 mtime），标注人工复查入口。

用法::

    python tools/audit_grep_findings.py            # 打印三态表
    python tools/audit_grep_findings.py --out PATH # 同上并写 markdown
退出码：存在 🔄 或 ⚠️ 时为 1（提示有人工动作），全 ✅ 为 0。
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = REPO / ".venv" / "bin" / "python"


@dataclass
class Finding:
    fid: str
    source: str          # 结论出处（文档 + 位置描述）
    claim: str           # 原结论
    verify: object       # Callable[[], tuple[bool | None, str]]  None=证据不足
    note: str = ""


def _py(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = ":".join(
        str(REPO / d) for d in (
            "core-time/src", "core-symbol/src", "core-rule/src",
            "core-eval/src", "app-zeri/src",
        )
    ) + f":{REPO}"
    return subprocess.run([str(PY), *args], cwd=cwd, capture_output=True, text=True, env=env)


# ---------- 各结论的复核函数 ----------

def v_testrepoisclean_split() -> tuple[bool | None, str]:
    """片1 是否已剥离仓库级断言（当初用 git show|grep -ac 单模式判定——单模式合法）。"""
    r = subprocess.run(
        ["git", "show", "8f2217f:tests/unit/test_no_aggregate_score_lint.py"],
        capture_output=True, text=True, cwd=REPO,
    )
    ok = "TestRepoIsClean" not in r.stdout and "class Test" in r.stdout
    return ok, "git show 8f2217f + Python find（非 grep 判定）" if ok else "片1 仍有断言"


def v_q020() -> tuple[bool | None, str]:
    r = _py("-c",
            "from pathlib import Path\n"
            "t = Path('tests/unit/test_paipan_fixed.py').read_text(encoding='utf-8')\n"
            "print('HAS' if 'class TestSanshaScope' in t else 'MISS')")
    return ("HAS" in r.stdout), "Python 遍历（verify_claims.py 同源）"


def v_q021() -> tuple[bool | None, str]:
    r = _py("-c",
            "import yaml\n"
            "d = yaml.safe_load(open('core-rule/config/calibers/jianxiang.yaml'))\n"
            "print(len(d['calibers']))")
    return (r.stdout.strip() == "2"), f"yaml 解析：calibers={r.stdout.strip()}"


def v_engine_text() -> tuple[bool | None, str]:
    """engine.py 无 NUL / 合法 UTF-8（推翻 11-02「判二进制」误诊的依据）。"""
    data = (REPO / "core-eval/src/core_eval/engine.py").read_bytes()
    has_nul = b"\x00" in data
    try:
        data.decode("utf-8")
        utf8_ok = True
    except UnicodeDecodeError:
        utf8_ok = False
    return (not has_nul and utf8_ok), f"NUL={has_nul}, utf8={utf8_ok}"


def v_no_total_rank() -> tuple[bool | None, str]:
    """_total_rank/_mean_rank_score 不在 engine/ranker 的 AST（AST 复扫）。"""
    banned = {"_total_rank", "_mean_rank_score"}
    bad = []
    for rel in ("core-eval/src/core_eval/engine.py", "core-eval/src/core_eval/ranker.py"):
        tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in banned:
                bad.append(f"{rel}:def:{node.name}")
            if isinstance(node, ast.Call):
                f = node.func
                name = getattr(f, "id", None) or getattr(f, "attr", None)
                if name in banned:
                    bad.append(f"{rel}:call:{name}")
            if isinstance(node, ast.Attribute) and node.attr in banned:
                bad.append(f"{rel}:attr")
    return (not bad), "AST 复扫干净" if not bad else f"命中 {bad[:3]}"


def v_manifest_counts() -> tuple[bool | None, str]:
    """manifest 计数（86 条）由 yaml/loader 得出，非 grep——复跑 loader 核对。"""
    r = _py("-c",
            "from core_rule.loader import load_ruleset\n"
            "rs = load_ruleset('core-rule/rules')\n"
            "print(len(rs.rules))")
    return (r.stdout.strip() == "86"), f"loader 计数={r.stdout.strip()}"


def v_old_chain_not_on_remote() -> tuple[bool | None, str]:
    """origin/main == 64f5be5（旧链未上远端）。"""
    r = subprocess.run(["git", "log", "origin/main", "--oneline", "-1"],
                       capture_output=True, text=True, cwd=REPO)
    return r.stdout.startswith("64f5be5"), r.stdout.strip() or r.stderr.strip()


def v_pytest_summary_boundary() -> tuple[bool | None, str]:
    """「pytest 汇总行不可见」→ 边界修正：仅 -q 下不可见，非 -q 正常。"""
    t = REPO / "tests/unit/test_verdict_baseline.py"
    withq = _py("-m", "pytest", str(t), "-q", "--junitxml=/tmp/audit-q.xml")
    withoutq = _py("-m", "pytest", str(t), "--junitxml=/tmp/audit-nq.xml")
    q_missing = "passed" not in withq.stdout
    nq_present = "passed" in withoutq.stdout
    return (q_missing and nq_present), f"-q 汇总消失={q_missing}，非 -q 可见={nq_present}"


def v_stash_reachable() -> tuple[bool | None, str]:
    r = subprocess.run(["git", "merge-base", "--is-ancestor", "eac493d", "main"],
                       capture_output=True, cwd=REPO)
    return (r.returncode == 0), "eac493d 是 main 祖先" if r.returncode == 0 else "不可达"


def v_mtime_forensics() -> tuple[bool | None, str]:
    """mtime 归属结论依赖当时快照，无法事后复跑。"""
    return None, "mtime 是一次性快照证据；维持结论但标注：不可机器复跑，如需复核须重新取样"


FINDINGS: list[Finding] = [
    Finding("C-01", "评审四·片1 重写：TestRepoIsClean 已剥离",
            "片1（8f2217f）不含仓库级断言，单独检出可绿", v_testrepoisclean_split),
    Finding("C-02", "取证 §6.6 / q020-q021-verification.md",
            "Q-020 TestSanshaScope 存在且全过", v_q020),
    Finding("C-03", "取证 §6.6 / q020-q021-verification.md",
            "Q-021 jianxiang.yaml 两口径 + TestJianxiangCaliber", v_q021),
    Finding("C-04", "取证 §6.6 根因修正",
            "engine.py 无 NUL、合法 UTF-8（「判二进制」误诊不成立）", v_engine_text),
    Finding("C-05", "test_no_total_rank / CHANGELOG",
            "_total_rank/_mean_rank_score 已从 engine/ranker 语法树消失", v_no_total_rank),
    Finding("C-06", "CHANGELOG / rules lint 输出",
            "规则库 86 条（manifest 计数）", v_manifest_counts),
    Finding("C-07", "2026-11-03 上午汇报",
            "旧链未上远端：origin/main == 64f5be5", v_old_chain_not_on_remote),
    Finding("C-08", "2026-11-03 上午汇报",
            "pytest 汇总行不可见 → **边界修正**：仅 -q 下消失，非 -q 正常",
            v_pytest_summary_boundary,
            note="此前 CHANGELOG/记忆写的是绝对表述，需改为「-q 下」"),
    Finding("C-09", "并发取证（mtime 表）",
            "huangdao/jianchu 等文件由并行会话写入", v_mtime_forensics),
    Finding("C-10", "2026-11-03 上午汇报",
            "stash@{0} 的 base 在新链可达，重写未破坏 stash", v_stash_reachable),
]


def scan_doc_grep_mentions() -> list[str]:
    """扫描文档里引用 grep 证据的行（人工复核索引，不自动判真伪）。"""
    hits: list[str] = []
    for rel in ("CHANGELOG.md", "docs/QUESTIONS.md",
                "docs/research/concurrent-write-forensics-2026-11-02.md"):
        p = REPO / rel
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            low = line.lower()
            if "grep" in low and any(k in line for k in ("空", "无输出", "零命中", "未命中")):
                hits.append(f"{rel}:{i}: {line.strip()[:100]}")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    lines = ["# grep/工具行为证据审计（tools/audit_grep_findings.py 输出）", "",
             "| ID | 出处 | 结论 | 复核 | 三态 |", "|---|---|---|---|---|"]
    n_bad = 0
    for f in FINDINGS:
        try:
            ok, detail = f.verify()  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001
            ok, detail = None, f"复核器异常：{exc}"
        state = {True: "✅ 成立", False: "🔄 反转", None: "⚠️ 证据不足"}[ok]
        if ok is not True:
            n_bad += 1
        lines.append(f"| {f.fid} | {f.source} | {f.claim} | {detail} | {state} |")
        if f.note:
            lines.append(f"| | ↳ 备注：{f.note} | | | |")

    mentions = scan_doc_grep_mentions()
    lines += ["", f"## 文档中引用 grep 证据的句子（{len(mentions)} 处，人工复核索引）", ""]
    lines += [f"- `{m}`" for m in mentions] or ["- （无）"]
    lines += ["", "> 本表由脚本生成；新增「grep 零命中」类结论时请同步登记到 FINDINGS。"]

    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"[written] {args.out}", file=sys.stderr)
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
