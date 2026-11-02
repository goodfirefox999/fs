"""静态一致性门槛的反证测试（2026-11-02 死模块事故）。

为什么每个 check 都要"先证明它会响，再证明它不乱响"
------------------------------------------------
lint 不变式最危险的失败模式是**恒真**：规则写得看起来对，但对任何输入都返回 []，
CI 永远绿、故障永远漏。所以每条 check 至少两个用例：
构造违规样本断言报警 + 移除触发条件断言沉默（AGENTS 纪律 3）。

这里用**合成仓库**（tmp_path 下按 SOURCE_ROOTS 摆文件）而不是真仓库，
因为真仓库的形态会变，合成样本才能锁住"什么条件下必须响"。
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml
from app_zeri.lint_static import (
    build_index,
    check_coverage_gaps,
    check_question_numbering,
    dead_derive_functions,
    unimported_modules,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def _repo(tmp: Path, *, called: bool, imported: bool) -> Path:
    _write(
        tmp / "core-symbol/src/core_symbol/model.py",
        """
        def derive_thing_facts(*, x):
            return {"x": x}
        """,
    )
    _write(
        tmp / "core-symbol/src/core_symbol/__init__.py",
        ("from .model import derive_thing_facts\n" if imported else "") + "from .lonely import lonely\n",
    )
    _write(
        tmp / "core-symbol/src/core_symbol/lonely.py",
        "def lonely():\n    return 1\n",
    )
    _write(
        tmp / "app-zeri/src/app_zeri/use.py",
        ("from core_symbol.model import derive_thing_facts\n\n"
         "def go():\n    return derive_thing_facts(x=1)\n") if called else "def go():\n    return 1\n",
    )
    return tmp


def _gaps(tmp: Path, body: dict) -> Path:
    path = tmp / "gaps.yaml"
    path.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
    return path


FACTS_OK = [("thing", "本系统提供")]
FACTS_ABSENT = [("thing", "本系统不提供")]


class TestDeadDerive:
    def test_flags_uncalled_derive(self, tmp_path: Path) -> None:
        idx = build_index(_repo(tmp_path, called=False, imported=True))
        msgs = dead_derive_functions(idx)
        assert len(msgs) == 1 and "derive_thing_facts" in msgs[0]

    def test_silent_when_called_from_other_file(self, tmp_path: Path) -> None:
        idx = build_index(_repo(tmp_path, called=True, imported=True))
        assert dead_derive_functions(idx) == []

    def test_call_inside_same_file_does_not_count(self, tmp_path: Path) -> None:
        """自调用不算接上：同一文件内互调仍是死代码（这正是 zibai 事故的形态）。

        只被「死函数」调用的 helper 也算死 —— 按 AGENTS 字面规则（无外部调用点即失败），
        报出来是噪音但方向安全；反过来放过它，就会留下"外层修好了、内层还是死"的缝。
        """
        _write(
            tmp_path / "core-symbol/src/core_symbol/selfref.py",
            """
            def derive_outer(*, x):
                return derive_inner(x=x)

            def derive_inner(*, x):
                return x
            """,
        )
        dead = dead_derive_functions(build_index(tmp_path))
        assert any("derive_outer" in m for m in dead)
        assert any("derive_inner" in m for m in dead)

    def test_helper_reached_from_live_function_is_not_dead(self, tmp_path: Path) -> None:
        """外层被外部调用时，同文件内层 helper 随之存活（传递闭包的正向用例）。"""
        _write(
            tmp_path / "core-symbol/src/core_symbol/chain.py",
            """
            def derive_outer(*, x):
                return derive_inner(x=x)

            def derive_inner(*, x):
                return x
            """,
        )
        _write(
            tmp_path / "app-zeri/src/app_zeri/use.py",
            "from core_symbol.chain import derive_outer\n\n"
            "def go():\n    return derive_outer(x=1)\n",
        )
        assert dead_derive_functions(build_index(tmp_path)) == []


class TestUnimportedModule:
    def test_flags_module_never_imported(self, tmp_path: Path) -> None:
        idx = build_index(_repo(tmp_path, called=True, imported=False))
        # lonely 在 __init__ 里被 import，故只有首次构造时才可能漏；这里换个孤立模块验证
        _write(tmp_path / "core-symbol/src/core_symbol/orphan.py", "X = 1\n")
        idx = build_index(tmp_path)
        msgs = unimported_modules(idx)
        assert msgs == ["core_symbol.orphan 未被任何非测试文件 import（模块存在但不在调用链上）"]

    def test_silent_when_imported(self, tmp_path: Path) -> None:
        _repo(tmp_path, called=True, imported=True)
        _write(tmp_path / "core-symbol/src/core_symbol/orphan.py", "X = 1\n")
        _write(
            tmp_path / "core-symbol/src/core_symbol/__init__.py",
            "from .model import derive_thing_facts\nfrom .lonely import lonely\nfrom .orphan import X\n",
        )
        assert unimported_modules(build_index(tmp_path)) == []


class TestCoverageGapConsistency:
    def _index(self, tmp_path: Path, *, called: bool):
        return build_index(_repo(tmp_path, called=called, imported=True))

    def _gap(self, status: str, roots: list[str], derives: list[str]) -> dict:
        return {
            "gaps": [
                {
                    "id": "GAP-TEST",
                    "implementation": {"status": status, "fact_roots": roots, "derive": derives},
                }
            ]
        }

    def test_unimplemented_but_fact_provided_is_error(self, tmp_path: Path) -> None:
        idx = self._index(tmp_path, called=False)
        path = _gaps(tmp_path, self._gap("unimplemented", ["thing"], []))
        msgs = check_coverage_gaps(path, fact_registry=FACTS_OK, index=idx)
        assert any("登记为「未实现」" in m for m in msgs)

    def test_unimplemented_and_absent_is_silent(self, tmp_path: Path) -> None:
        idx = self._index(tmp_path, called=False)
        path = _gaps(tmp_path, self._gap("unimplemented", ["thing"], []))
        assert check_coverage_gaps(path, fact_registry=FACTS_ABSENT, index=idx) == []

    def test_unimplemented_but_derive_called_is_error(self, tmp_path: Path) -> None:
        idx = self._index(tmp_path, called=True)
        path = _gaps(tmp_path, self._gap("unimplemented", ["thing"], ["derive_thing_facts"]))
        msgs = check_coverage_gaps(path, fact_registry=FACTS_ABSENT, index=idx)
        assert any("已有调用点" in m for m in msgs)

    def test_implemented_but_no_call_is_error(self, tmp_path: Path) -> None:
        """这正是 2026-11-02 的形态：登记说已实现，代码里没人调。"""
        idx = self._index(tmp_path, called=False)
        path = _gaps(tmp_path, self._gap("implemented", ["thing"], ["derive_thing_facts"]))
        msgs = check_coverage_gaps(path, fact_registry=FACTS_OK, index=idx)
        assert any("无调用点" in m for m in msgs)

    def test_implemented_and_wired_is_silent(self, tmp_path: Path) -> None:
        idx = self._index(tmp_path, called=True)
        path = _gaps(tmp_path, self._gap("implemented", ["thing"], ["derive_thing_facts"]))
        assert check_coverage_gaps(path, fact_registry=FACTS_OK, index=idx) == []

    def test_implemented_but_fact_missing_is_error(self, tmp_path: Path) -> None:
        idx = self._index(tmp_path, called=True)
        path = _gaps(tmp_path, self._gap("implemented", ["thing"], []))
        msgs = check_coverage_gaps(path, fact_registry=FACTS_ABSENT, index=idx)
        assert any("均未在 FACT_REGISTRY 提供" in m for m in msgs)

    def test_illegal_status_is_error(self, tmp_path: Path) -> None:
        idx = self._index(tmp_path, called=True)
        path = _gaps(tmp_path, self._gap("maybe", ["thing"], []))
        assert any("implementation.status 非法" in m for m in check_coverage_gaps(
            path, fact_registry=FACTS_OK, index=idx))

    def test_gap_without_implementation_block_is_skipped(self, tmp_path: Path) -> None:
        """非实现类缺口（防线/产品信息）不要求 implementation 块。"""
        idx = self._index(tmp_path, called=True)
        path = _gaps(tmp_path, {"gaps": [{"id": "GAP-INFO", "claim": "产品级信息"}]})
        assert check_coverage_gaps(path, fact_registry=FACTS_OK, index=idx) == []


class TestRealRepoBaseline:
    """真仓库当前状态必须干净——它是这两条门槛的"零假设"。"""

    def test_real_repo_passes(self) -> None:
        root = Path(__file__).resolve().parents[2]
        idx = build_index(root)
        assert dead_derive_functions(idx) == []
        assert unimported_modules(idx) == []


class TestQuestionNumbering:
    """裁定记录编号的唯一性/连续性（并发追加的审计链防线）。"""

    def _file(self, tmp_path: Path, body: str) -> Path:
        path = tmp_path / "QUESTIONS.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_clean_sequence_is_silent(self, tmp_path: Path) -> None:
        path = self._file(tmp_path, "## Q-001 甲\n\n正文\n\n## Q-002 乙\n")
        assert check_question_numbering(path) == []

    def test_duplicate_is_error(self, tmp_path: Path) -> None:
        body = "## Q-001 甲\n\n## Q-002 乙\n\n## Q-001 丙\n"
        msgs = check_question_numbering(self._file(tmp_path, body))
        assert any("编号重复" in m and "Q-001" in m for m in msgs)

    def test_gap_is_error(self, tmp_path: Path) -> None:
        body = "## Q-001 甲\n\n## Q-003 丙\n"
        msgs = check_question_numbering(self._file(tmp_path, body))
        assert any("断号" in m and "Q-002" in m for m in msgs)

    def test_disposition_heading_does_not_collide(self, tmp_path: Path) -> None:
        """`## 处置更新 · Q-001` 不是新条目，不得被计入编号序列。"""
        body = "## Q-001 甲\n\n## Q-002 乙\n\n## 处置更新 · Q-001：已落地\n"
        assert check_question_numbering(self._file(tmp_path, body)) == []

    def test_missing_file_is_silent(self, tmp_path: Path) -> None:
        assert check_question_numbering(tmp_path / "absent.md") == []

    def test_real_repo_is_clean(self) -> None:
        root = Path(__file__).resolve().parents[2]
        assert check_question_numbering(root / "docs" / "QUESTIONS.md") == []
