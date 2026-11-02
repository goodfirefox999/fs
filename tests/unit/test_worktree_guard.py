"""工作区守卫的纯函数测试（并发写入事故的流程化处置）。

守卫本身只读 `git status`，不适合在单测里跑真仓库（结果随工作区变化）。
故只测 ``classify``：噪声/白名单/需确认三分是否按预期分流。
"""

from __future__ import annotations

from tools.worktree_guard import classify


class TestClassify:
    def test_noise_is_ignored(self) -> None:
        entries = [("??", "core-symbol/src/core_symbol/__pycache__/x.cpython-314.pyc")]
        assert classify(entries, [])["review"] == []

    def test_whitelist_matches_glob(self) -> None:
        entries = [(" M", "core-symbol/src/core_symbol/xiu.py")]
        buckets = classify(entries, ["core-symbol/*"])
        assert buckets["allowed"] == ["core-symbol/src/core_symbol/xiu.py"]
        assert buckets["review"] == []

    def test_foreign_change_requires_review(self) -> None:
        """他进程写的文件（不在本次白名单）必须落到 review，而不是静默通过。"""
        entries = [("??", "core-symbol/src/core_symbol/huangdao.py")]
        buckets = classify(entries, ["core-symbol/src/core_symbol/xiu.py"])
        assert buckets["review"] == ["core-symbol/src/core_symbol/huangdao.py"]

    def test_three_buckets_partition_all_entries(self) -> None:
        entries = [
            (" M", ".coverage"),
            (" M", "README.md"),
            ("??", "docs/research/x.md"),
        ]
        buckets = classify(entries, ["README.md"])
        total = sum(len(v) for v in buckets.values())
        assert total == len(entries)
        assert buckets["noise"] == [".coverage"]
        assert buckets["allowed"] == ["README.md"]
        assert buckets["review"] == ["docs/research/x.md"]
