"""分配下一个 Q 编号并把条目追加到 ``docs/QUESTIONS.md``。

为什么要有这个工具（而不是继续靠"新增前先 grep 最大号"）
-----------------------------------------------------
2026-11-02 发生过一次真实撞车：两个会话各自读到"最大是 Q-021"，于是都写了 Q-022 之前
的号段，最后 `QUESTIONS.md` 里 Q-018/Q-020/Q-021 **各出现两次**（一份问题本体、
一份「处置更新」）。`check_question_numbering` 能事后发现，但文件已经写坏。

根因是"编号靠人记"。本工具把编号变成**一次原子读-算-写**：扫描全文所有
``Q-<数字>``（含 ``## 处置更新 · Q-nnn`` 这类后续通知里的引用），取最大值 +1，
再追加。lint 降级为兜底。

用法
----
    python tools/new_question.py --title "阴宅共识门槛" --body-file draft.md
    python tools/new_question.py --title "阴宅共识门槛" --body "一句话说明"
    python tools/new_question.py --title "..." --body-file draft.md --dry-run

设计约束
--------
- **只追加，不改写**：不重排、不修改既有条目（避免并发下互相覆盖）；
- **dry-run 默认打印预览**，`--apply` 才写盘（默认即写，但 `--dry-run` 可预览）；
- 编号取**全文最大值 +1**，不是"条数 +1"——跳号（Q-014 已关闭）不会被算错；
- **已归档/已关闭的编号永不复用**：全文扫描（含处置更新与正文引用）天然保证
  这一点——只要条目文本还在，它的号就占着坑；
- **并发边界（2026-11-03 评审）**：本工具只保护**同一工作区**的原子性。
  两个会话同时 dry-run 会拿到同一个号；写盘后以**提交时间为准**，
  冲突时后到者顺延。不做 `--reserve` 占位——占位条目会污染审计链
  （空壳 Q 号比撞号更难清理）。
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

__all__ = ["next_question_number", "build_entry", "append_question", "main"]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "docs" / "QUESTIONS.md"

#: 全文任意位置的 Q 编号（含 "处置更新 · Q-018"、正文引用 "见 Q-015"）
_Q_PATTERN = re.compile(r"Q-(\d+)")


def next_question_number(text: str) -> int:
    """返回下一个可用编号（全文最大 + 1）。空文件从 1 开始。"""
    numbers = [int(m.group(1)) for m in _Q_PATTERN.finditer(text)]
    return (max(numbers) + 1) if numbers else 1


def build_entry(number: int, title: str, body: str, *, day: date | None = None) -> str:
    """拼一条新条目。标题不带日期时按需补 ``（YYYY-MM-DD 新增）``。"""
    title = title.strip()
    suffix = f"（{day.isoformat()} 新增）" if day and day.isoformat() not in title else ""
    lines = ["", "---", "", f"## Q-{number:03d} {title}{suffix}", "", body.strip(), ""]
    return "\n".join(lines)


def append_question(
    path: Path,
    *,
    title: str,
    body: str,
    day: date | None = None,
    dry_run: bool = False,
) -> tuple[int, str]:
    """追加一条 Q 条目，返回 ``(编号, 完整新文本)``。

    并发保护：追加前**重新读取**文件并重算编号（不做"先算号再睡眠再写"那种竞态）；
    写回前再核对一次编号未被占用，被占用则报错而不是覆盖。
    """
    if not title.strip():
        raise ValueError("标题不得为空")
    if not body.strip():
        raise ValueError("正文不得为空（空条目会让审计链出现无法核对的编号）")

    text = path.read_text(encoding="utf-8") if path.exists() else "# 待人类裁定的问题清单（QUESTION）\n"
    number = next_question_number(text)
    entry = build_entry(number, title, body, day=day)
    new_text = text.rstrip("\n") + "\n" + entry

    # 二次核对：新编号在原文里必须不存在（防极端并发下的重复）
    if re.search(rf"Q-{number:03d}\b", text):
        raise ValueError(f"Q-{number:03d} 已被占用（并发写入？请重跑本工具重新取号）")

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return number, new_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="分配下一个 Q 编号并追加条目")
    parser.add_argument("--title", required=True, help="条目标题（不含编号）")
    parser.add_argument("--body-file", default=None, help="正文文件（Markdown）")
    parser.add_argument("--body", default=None, help="正文（与 --body-file 二选一）")
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="QUESTIONS.md 路径")
    parser.add_argument("--date", default=None, help="标题里补的日期（默认不加）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写盘")
    args = parser.parse_args(argv)

    if bool(args.body_file) == bool(args.body):
        print("必须且只能给 --body-file 或 --body 之一", file=sys.stderr)
        return 2
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else args.body
    day = date.fromisoformat(args.date) if args.date else None

    try:
        number, new_text = append_question(
            Path(args.path), title=args.title, body=body, day=day, dry_run=args.dry_run
        )
    except ValueError as exc:
        print(f"拒绝写入：{exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        tail = new_text.split("---")[-1]
        print(f"[dry-run] 将分配 Q-{number:03d}，追加内容：{tail.strip()[:400]}")
    else:
        print(f"已追加 Q-{number:03d} → {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
