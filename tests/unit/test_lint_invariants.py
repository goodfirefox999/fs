"""lint 不变式的反证测试（AGENTS.md 补丁纪律第 3 条：每条不变式必须配反证）。

模板：
1. **构造违规样本 → 断言报警**（证明检查真的在检查）；
2. **移除触发条件 → 断言沉默**（证明不是"永远报警"）。

只断言"当前恰好为空"不算验证——那在检查被删掉时也照样通过。
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import yaml

from app_zeri.cli import _check_calibers, _check_no_float_literals
from core_rule import default_registry


class TestCaliberDefaultRequired:
    """口径文件必须显式声明 default，不得依赖 YAML 首个键（顺序依赖）。"""

    def _write(self, tmp_path, body: dict) -> None:
        (tmp_path / "sample.yaml").write_text(
            yaml.safe_dump(body, allow_unicode=True), encoding="utf-8"
        )

    def test_missing_default_is_reported(self, tmp_path) -> None:
        self._write(
            tmp_path,
            {
                "caliber_set": "sample",
                # 故意不写 default —— 旧加载器会取第一个键 a
                "calibers": {"a": {"status": "待考证"}, "b": {"status": "待考证"}},
            },
        )
        problems = _check_calibers(tmp_path)
        assert len(problems) == 1
        assert "未显式声明 default" in problems[0]

    def test_explicit_default_is_silent(self, tmp_path) -> None:
        """移除触发条件（补上 default）后必须沉默。"""
        self._write(
            tmp_path,
            {
                "caliber_set": "sample",
                "default": "b",
                "calibers": {"a": {"status": "待考证"}, "b": {"status": "待考证"}},
            },
        )
        assert _check_calibers(tmp_path) == []

    def test_empty_default_string_is_reported(self, tmp_path) -> None:
        """`default:` 留空等同未声明（YAML 解析成 None），不能算通过。"""
        self._write(
            tmp_path,
            {"caliber_set": "sample", "default": None, "calibers": {"a": {"status": "待考证"}}},
        )
        assert _check_calibers(tmp_path)

    def test_real_caliber_dir_is_clean(self) -> None:
        """真实口径目录必须全绿——否则上面三条只是在自娱自乐。"""
        assert _check_calibers() == []


class TestNoFloatLiterals:
    """规则条件禁止浮点字面量（数值用整数或整数比）。"""

    @staticmethod
    def _reg_with_condition(condition: dict) -> SimpleNamespace:
        base = default_registry().ruleset.rules[0]
        return SimpleNamespace(ruleset=SimpleNamespace(rules=[replace(base, condition=condition)]))

    def test_float_in_condition_is_reported(self) -> None:
        reg = self._reg_with_condition(
            {"fact": "facts.tongguan.wuxing_count.木", "op": "gte", "value": 2.5}
        )
        problems = _check_no_float_literals(reg)
        assert len(problems) == 1
        assert "浮点字面量" in problems[0]

    def test_nested_float_is_reported(self) -> None:
        """嵌套在 all/between 里的浮点也要抓到（只查顶层等于没查）。"""
        reg = self._reg_with_condition(
            {
                "all": [
                    {"fact": "site.offset_deg", "op": "between", "value": [-7.5, 7.5]},
                ]
            }
        )
        assert len(_check_no_float_literals(reg)) == 2  # 两个边界各报一条

    def test_integer_condition_is_silent(self) -> None:
        """移除触发条件（改整数/整数比）后必须沉默。"""
        reg = self._reg_with_condition(
            {"fact": "facts.tongguan.wuxing_count.木", "op": "gte", "value": 2}
        )
        assert _check_no_float_literals(reg) == []

    def test_string_and_bool_are_silent(self) -> None:
        """字符串/布尔不是浮点：`in [破, 闭]`、`eq true` 不得误报。"""
        reg = self._reg_with_condition({"fact": "facts.jianchu.star", "op": "in", "value": ["破", "闭"]})
        assert _check_no_float_literals(reg) == []

    def test_real_ruleset_is_clean(self) -> None:
        """真实规则库必须全绿——这是"禁止新增浮点条件"的实际门禁。"""
        assert _check_no_float_literals(default_registry()) == []
