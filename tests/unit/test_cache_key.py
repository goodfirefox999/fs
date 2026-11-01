"""C19 统一缓存键测试：单一函数 + 手写 key lint。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core_time.hashing import KEY_SCHEMA, stable_cache_key

ROOT = Path(__file__).resolve().parents[2]


class TestStableCacheKey:
    def test_deterministic(self) -> None:
        a = stable_cache_key("select_rules", ("a", "b"), 1, None, True)
        b = stable_cache_key("select_rules", ("a", "b"), 1, None, True)
        assert a == b

    def test_distinct_parts_distinct_keys(self) -> None:
        parts = [
            ("x", 1),
            ("x", 2),
            ("x", (1, 2)),
            ("x", [1, 2]),  # tuple/list 归一后与上一项同键
        ]
        keys = [stable_cache_key(p) for p in parts]
        assert keys[0] != keys[1]
        assert keys[2] == keys[3], "tuple 与 list 归一为同一键"

    def test_dict_key_order_insensitive(self) -> None:
        assert stable_cache_key({"a": 1, "b": 2}) == stable_cache_key({"b": 2, "a": 1})

    def test_schema_version_prefix(self) -> None:
        assert stable_cache_key("x").startswith(f"{KEY_SCHEMA}:")

    def test_key_length_bounded(self) -> None:
        """键为定长哈希，parts 再长也不膨胀缓存键。"""
        assert len(stable_cache_key(*range(1000))) < 80


class TestLint:
    def test_lint_passes_on_current_tree(self) -> None:
        r = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "cache_key_lint.py")],
            capture_output=True, text=True, timeout=120,
        )
        assert r.returncode == 0, r.stdout + r.stderr

    def test_lint_flags_handwritten_composite_key(self, tmp_path) -> None:
        """手写组合键必须被 lint 拦截。"""
        pkg = tmp_path / "src"
        pkg.mkdir(parents=True)
        (pkg / "bad.py").write_text(
            "MY_CACHE: dict = {}\n"
            "def f(k: tuple) -> None:\n"
            "    MY_CACHE[k] = 1\n",
            encoding="utf-8",
        )
        from tools.cache_key_lint import scan_file

        problems = scan_file(pkg / "bad.py")
        assert any("未过 stable_cache_key" in p for p in problems), problems

    def test_lint_accepts_helper_key_and_var(self, tmp_path) -> None:
        """经 helper 直接构造或同作用域变量均放行。"""
        pkg = tmp_path / "src"
        pkg.mkdir(parents=True)
        (pkg / "ok.py").write_text(
            "from core_time.hashing import stable_cache_key\n"
            "MY_CACHE: dict = {}\n"
            "def f(a) -> None:\n"
            "    k = stable_cache_key('x', a)\n"
            "    MY_CACHE[k] = 1\n"
            "    MY_CACHE[stable_cache_key('y', a)] = 2\n",
            encoding="utf-8",
        )
        from tools.cache_key_lint import scan_file

        assert scan_file(pkg / "ok.py") == []

    def test_lint_requires_exempt_marker_for_lru(self, tmp_path) -> None:
        pkg = tmp_path / "src"
        pkg.mkdir(parents=True)
        (pkg / "nolru.py").write_text(
            "from functools import lru_cache\n\n"
            "@lru_cache(maxsize=8)\n"
            "def f(x: int) -> int:\n"
            "    return x\n",
            encoding="utf-8",
        )
        from tools.cache_key_lint import scan_file

        problems = scan_file(pkg / "nolru.py")
        assert any("C19-exempt" in p for p in problems), problems
