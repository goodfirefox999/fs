"""`tools/new_question.py` 的测试：编号分配必须"从源头"正确。

核心断言只有一条但很关键：编号取**全文最大 +1**，而不是"条目数 +1"，
也不是"只看 `## Q-` 标题的最大值"。后者正是 2026-11-02 撞车的成因——
`## 处置更新 · Q-021` 里的 021 不进标题扫描，下一条就又会分到 022。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tools.new_question import append_question, build_entry, next_question_number

SAMPLE = """# 待人类裁定的问题清单

## Q-001 甲

正文

---

## Q-002 乙

正文

---

## 处置更新 · Q-002（2026-11-02）：已落地

说明
"""


class TestNextNumber:
    def test_max_plus_one(self) -> None:
        assert next_question_number(SAMPLE) == 3

    def test_counts_disposition_updates(self) -> None:
        """只在「处置更新」里出现的更大编号也必须计入。"""
        text = "## Q-001 甲\n\n## 处置更新 · Q-007：已处理\n"
        assert next_question_number(text) == 8

    def test_not_count_based(self) -> None:
        """跳号（Q-001、Q-005）时给出 6，而不是 3。"""
        text = "## Q-001 甲\n\n## Q-005 戊\n"
        assert next_question_number(text) == 6

    def test_empty_file_starts_at_one(self) -> None:
        assert next_question_number("") == 1

    def test_body_reference_also_counts(self) -> None:
        """正文里"见 Q-015"也算占用，避免后人拿它当新号。"""
        assert next_question_number("## Q-001 甲\n\n详见 Q-015。\n") == 16


class TestBuildEntry:
    def test_heading_format(self) -> None:
        entry = build_entry(3, "阴宅门槛", "正文")
        assert "## Q-003 阴宅门槛" in entry
        assert entry.startswith("\n---\n")

    def test_optional_date_suffix(self) -> None:
        entry = build_entry(3, "阴宅门槛", "正文", day=date(2026, 11, 3))
        assert "（2026-11-03 新增）" in entry

    def test_no_duplicate_suffix(self) -> None:
        entry = build_entry(3, "阴宅门槛（2026-11-03 新增）", "正文", day=date(2026, 11, 3))
        assert entry.count("2026-11-03") == 1


class TestAppend:
    def test_appends_and_returns_number(self, tmp_path: Path) -> None:
        path = tmp_path / "Q.md"
        path.write_text(SAMPLE, encoding="utf-8")
        number, text = append_question(path, title="丙", body="内容")
        assert number == 3
        assert "## Q-003 丙" in path.read_text(encoding="utf-8")
        assert text.rstrip().endswith("内容")

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        path = tmp_path / "Q.md"
        path.write_text(SAMPLE, encoding="utf-8")
        before = path.read_text(encoding="utf-8")
        append_question(path, title="丙", body="内容", dry_run=True)
        assert path.read_text(encoding="utf-8") == before

    def test_empty_body_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "Q.md"
        path.write_text(SAMPLE, encoding="utf-8")
        with pytest.raises(ValueError, match="正文不得为空"):
            append_question(path, title="丙", body="   ")

    def test_empty_title_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "Q.md"
        path.write_text(SAMPLE, encoding="utf-8")
        with pytest.raises(ValueError, match="标题不得为空"):
            append_question(path, title="  ", body="正文")

    def test_second_append_gets_next_number(self, tmp_path: Path) -> None:
        path = tmp_path / "Q.md"
        path.write_text(SAMPLE, encoding="utf-8")
        assert append_question(path, title="丙", body="内容")[0] == 3
        assert append_question(path, title="丁", body="内容")[0] == 4
