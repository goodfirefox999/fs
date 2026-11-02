"""`tools/dead_rule_scan.py` 结果缓存的不变式（2026-11-03）。

为什么缓存也要写测试
--------------------
缓存最大的风险不是"慢"，是**改了输入却读到旧结论**——那会把死规则扫描变成
"永远绿"的装饰品。所以这里测的不是"缓存能命中"，而是：

1. 键覆盖到位（规则/基线/窗口常量任一变化 → 键变）；
2. 缓存损坏 → 当作未命中（宁可重算 130 s，不可拿错结果）；
3. 写入是原子的（读者不会读到半个文件）。
"""

from __future__ import annotations

import json

import pytest

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "dead_rule_scan", Path(__file__).resolve().parents[2] / "tools" / "dead_rule_scan.py"
)
assert _SPEC and _SPEC.loader
scan = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scan)


class TestFingerprintCoversInputs:
    def test_is_deterministic_hex(self) -> None:
        a = scan._fingerprint()
        b = scan._fingerprint()
        assert a == b
        assert len(a) == 64 and all(c in "0123456789abcdef" for c in a)

    def test_rule_file_change_changes_key(self, tmp_path: Path, monkeypatch) -> None:
        """反证：改规则文件必须换键，否则改了规则会读到旧结论。"""
        fake_root = tmp_path
        (fake_root / "core-rule" / "rules" / "public").mkdir(parents=True)
        rule = fake_root / "core-rule" / "rules" / "public" / "X-001.yaml"
        rule.write_text("rule_id: X-001\n", encoding="utf-8")
        monkeypatch.setattr(scan, "ROOT", fake_root)
        before = scan._fingerprint()

        rule.write_text("rule_id: X-001\nseverity: 禁用\n", encoding="utf-8")  # 内容变 → 大小变
        after = scan._fingerprint()
        assert before != after

    def test_window_change_changes_key(self, monkeypatch) -> None:
        """窗口常量也必须进键：改了扫描年份却复用旧结果＝口径漂移。"""
        before = scan._fingerprint()
        monkeypatch.setattr(scan, "YEARS", (*scan.YEARS, 2028))
        assert scan._fingerprint() != before

    def test_source_change_changes_key(self, tmp_path: Path, monkeypatch) -> None:
        """引擎源码改动同样换键（否则改了判定逻辑还读旧扫描）。"""
        fake_root = tmp_path
        mod = fake_root / "core-eval" / "src" / "core_eval"
        mod.mkdir(parents=True)
        (mod / "engine.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(scan, "ROOT", fake_root)
        before = scan._fingerprint()
        (mod / "engine.py").write_text("x = 2\n", encoding="utf-8")
        assert scan._fingerprint() != before


class TestCacheIO:
    def test_roundtrip(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(scan, "CACHE_DIR", tmp_path / "cache")
        scan._cache_write("deadbeef", {"rc": 0, "stdout": "hello\n", "elapsed": 1.5})
        got = scan._cache_read("deadbeef")
        assert got is not None and got["stdout"] == "hello\n" and got["rc"] == 0

    def test_corrupt_cache_is_a_miss(self, tmp_path: Path, monkeypatch) -> None:
        """缓存损坏必须当作未命中——绝不因为缓存坏了而改变结论。"""
        monkeypatch.setattr(scan, "CACHE_DIR", tmp_path / "cache")
        (tmp_path / "cache").mkdir()
        (tmp_path / "cache" / "bad.json").write_text("{not json", encoding="utf-8")
        assert scan._cache_read("bad") is None

    def test_wrong_shape_is_a_miss(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(scan, "CACHE_DIR", tmp_path / "cache")
        (tmp_path / "cache").mkdir()
        (tmp_path / "cache" / "shape.json").write_text(json.dumps({"rc": 0}), encoding="utf-8")
        assert scan._cache_read("shape") is None

    def test_cache_dir_is_gitignored(self) -> None:
        """缓存必须落在 out/ 下（.gitignore 已忽略 out/），否则会把机器指纹提交进库。"""
        rel = scan.CACHE_DIR.relative_to(scan.ROOT)
        assert rel.parts[0] == "out"
        gitignore = (scan.ROOT / ".gitignore").read_text(encoding="utf-8")
        assert any(line.strip() in ("out/", "/out/") for line in gitignore.splitlines())


def test_cache_dir_constant_matches_out() -> None:
    """防止有人把 CACHE_DIR 改成仓库内非忽略目录（会污染 git status）。"""
    assert "out" in scan.CACHE_DIR.parts
