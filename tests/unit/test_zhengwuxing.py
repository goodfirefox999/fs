"""正五行扶山 facts 层测试。

三层：
1. **表层**：二十四山正五行表、生克关系表、旺相休囚死；
2. **事实层**：``derive_zhengwuxing_facts`` 的逐柱关系、计数、审计链；
3. **边界**：只输出关系，不输出任何吉凶／档位／分值字段（Q-029 未裁定前）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core_symbol.zhengwuxing import (
    ELEMENTS,
    RELATIONS,
    SHAN_WUXING_24,
    derive_bulong_facts,
    derive_xiangzhu_facts,
    derive_zhengwuxing_facts,
    month_stage_of,
    relation_of,
)

#: 乾山验收盘：丁未年 丁未月 甲午日 己巳时
ACCEPT_GANS = ["丁", "丁", "甲", "己"]
ACCEPT_ZHIS = ["未", "未", "午", "巳"]
ACCEPT_MONTH_ZHI = "未"


class TestTables:
    def test_covers_all_24_mountains(self) -> None:
        from core_symbol.mountain import MOUNTAINS_24

        assert set(SHAN_WUXING_24) == set(MOUNTAINS_24)
        assert len(SHAN_WUXING_24) == 24

    def test_four_weishan_elements(self) -> None:
        """四维山：乾金、坤土、艮土、巽木。"""
        assert SHAN_WUXING_24["乾"] == "金"
        assert SHAN_WUXING_24["坤"] == "土"
        assert SHAN_WUXING_24["艮"] == "土"
        assert SHAN_WUXING_24["巽"] == "木"

    def test_distribution(self) -> None:
        from collections import Counter

        dist = Counter(SHAN_WUXING_24.values())
        assert dist == {"水": 4, "土": 6, "木": 5, "火": 4, "金": 5}

    def test_all_relations_covered(self) -> None:
        seen = {relation_of(wo, ta) for wo in ELEMENTS for ta in ELEMENTS}
        assert seen == set(RELATIONS)


class TestRelation:
    @pytest.mark.parametrize(
        ("wo", "ta", "expected"),
        [
            ("木", "木", "比和"),
            ("木", "水", "生入"),
            ("木", "金", "克入"),
            ("木", "火", "生出"),
            ("木", "土", "克出"),
            ("火", "木", "生入"),
            ("火", "水", "克入"),
            ("火", "土", "生出"),
            ("火", "金", "克出"),
            ("土", "火", "生入"),
            ("土", "木", "克入"),
            ("土", "金", "生出"),
            ("土", "水", "克出"),
            ("金", "土", "生入"),
            ("金", "火", "克入"),
            ("金", "水", "生出"),
            ("金", "木", "克出"),
            ("水", "金", "生入"),
            ("水", "土", "克入"),
            ("水", "木", "生出"),
            ("水", "火", "克出"),
        ],
    )
    def test_pairs(self, wo: str, ta: str, expected: str) -> None:
        assert relation_of(wo, ta) == expected

    def test_direction_is_not_symmetric(self) -> None:
        """生入 ≠ 生出：方向一旦写反，整条链路的口径就错了。"""
        assert relation_of("木", "水") == "生入"
        assert relation_of("水", "木") == "生出"

    def test_invalid_element_rejected(self) -> None:
        with pytest.raises(ValueError):
            relation_of("风", "水")


class TestMonthStage:
    @pytest.mark.parametrize(
        ("element", "month_zhi", "expected"),
        [
            ("木", "寅", "旺"),
            ("火", "寅", "相"),
            ("水", "寅", "休"),
            ("金", "寅", "囚"),
            ("土", "寅", "死"),
            ("火", "午", "旺"),
            ("土", "午", "相"),
            ("木", "午", "休"),
            ("水", "午", "囚"),
            ("金", "午", "死"),
            ("金", "申", "旺"),
            ("土", "辰", "旺"),  # 四季土
            ("金", "未", "相"),  # 土生金
        ],
    )
    def test_stage(self, element: str, month_zhi: str, expected: str) -> None:
        assert month_stage_of(element, month_zhi) == expected

    def test_invalid_month_rejected(self) -> None:
        with pytest.raises(ValueError):
            month_stage_of("木", "子丑")


class TestFacts:
    def test_qian_mountain_acceptance(self) -> None:
        fx = derive_zhengwuxing_facts(
            mountain="乾",
            gans=ACCEPT_GANS,
            zhis=ACCEPT_ZHIS,
            month_zhi=ACCEPT_MONTH_ZHI,
        )
        assert fx["shan"] == {"name": "乾", "element": "金", "month_stage": "相"}
        assert fx["month"] == {"zhi": "未", "season": "四季", "season_element": "土"}
        assert len(fx["pillars"]) == 4
        assert [p["label"] for p in fx["pillars"]] == ["年", "月", "日", "时"]

        by_label = {p["label"]: p for p in fx["pillars"]}
        # 金我：火克金→克入；土生金→生入；木被金克→克出
        assert (by_label["年"]["gan_element"], by_label["年"]["gan_relation"]) == ("火", "克入")
        assert (by_label["年"]["zhi_element"], by_label["年"]["zhi_relation"]) == ("土", "生入")
        assert by_label["日"]["gan_relation"] == "克出"
        assert by_label["日"]["zhi_relation"] == "克入"

        assert fx["gan_counts"] == {"比和": 0, "生入": 1, "克入": 2, "生出": 0, "克出": 1}
        assert fx["zhi_counts"] == {"比和": 0, "生入": 2, "克入": 2, "生出": 0, "克出": 0}
        assert sum(fx["gan_counts"].values()) == 4
        assert sum(fx["zhi_counts"].values()) == 4

    def test_xun_mountain_flips_relations(self) -> None:
        """同一盘换巽山（木）：生克方向整体翻转，证明「我」取自坐山。"""
        fx = derive_zhengwuxing_facts(
            mountain="巽",
            gans=ACCEPT_GANS,
            zhis=ACCEPT_ZHIS,
            month_zhi=ACCEPT_MONTH_ZHI,
        )
        assert fx["shan"]["element"] == "木"
        assert fx["gan_counts"] == {"比和": 1, "生入": 0, "克入": 0, "生出": 2, "克出": 1}
        assert fx["zhi_counts"] == {"比和": 0, "生入": 0, "克入": 0, "生出": 2, "克出": 2}

        qian = derive_zhengwuxing_facts(
            mountain="乾",
            gans=ACCEPT_GANS,
            zhis=ACCEPT_ZHIS,
            month_zhi=ACCEPT_MONTH_ZHI,
        )
        # 反转必须能由审计链解释：第 1 步「我」的五行不同，第 3 步输入随之不同
        assert qian["audit_chain"][0]["output"]["element"] == "金"
        assert fx["audit_chain"][0]["output"]["element"] == "木"
        assert qian["audit_chain"][2]["input"]["shan_element"] == "金"
        assert fx["audit_chain"][2]["input"]["shan_element"] == "木"

    def test_audit_chain_is_complete(self) -> None:
        fx = derive_zhengwuxing_facts(
            mountain="乾",
            gans=ACCEPT_GANS,
            zhis=ACCEPT_ZHIS,
            month_zhi=ACCEPT_MONTH_ZHI,
        )
        chain = fx["audit_chain"]
        assert [s["step"] for s in chain] == [1, 2, 3, 4, 5, 6, 7]
        assert [s["what"] for s in chain] == [
            "坐山正五行",
            "月令旺衰",
            "年柱生克",
            "月柱生克",
            "日柱生克",
            "时柱生克",
            "关系计数",
        ]
        for step in chain:
            assert set(step) == {"step", "what", "input", "output"}
        assert chain[-1]["output"] == {
            "gan_counts": fx["gan_counts"],
            "zhi_counts": fx["zhi_counts"],
        }

    def test_no_judgment_fields(self) -> None:
        """Q-029 未裁定前，事实层不得出现吉凶／档位／分值。"""
        fx = derive_zhengwuxing_facts(
            mountain="乾",
            gans=ACCEPT_GANS,
            zhis=ACCEPT_ZHIS,
            month_zhi=ACCEPT_MONTH_ZHI,
        )

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    assert key not in {"grade", "verdict", "score", "weight"}, path + "/" + key
                    walk(value, f"{path}/{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, f"{path}[{i}]")
            elif node in {"大吉", "吉", "平", "凶", "大凶"}:
                raise AssertionError(f"事实层出现吉凶判断: {path} = {node!r}")

        walk({k: v for k, v in fx.items() if k != "note"})
        assert fx["status"] == "待考证"
        assert "不判吉凶" in fx["note"]

    def test_short_pillar_list_not_padded(self) -> None:
        """缺项按实际长度输出：只有两柱时不得补默认干支。"""
        fx = derive_zhengwuxing_facts(
            mountain="乾", gans=["丁", "丁"], zhis=["未", "未"], month_zhi="未"
        )
        assert len(fx["pillars"]) == 2
        assert sum(fx["gan_counts"].values()) == 2

    def test_unknown_mountain_rejected(self) -> None:
        with pytest.raises(ValueError):
            derive_zhengwuxing_facts(
                mountain="中", gans=ACCEPT_GANS, zhis=ACCEPT_ZHIS, month_zhi="未"
            )

    def test_invalid_branch_rejected(self) -> None:
        with pytest.raises(ValueError):
            derive_zhengwuxing_facts(
                mountain="乾", gans=["丁"], zhis=["子丑"], month_zhi="未"
            )

    def test_length_mismatch_rejected(self) -> None:
        """数量不一致必须报错，不能 zip 静默截断。"""
        with pytest.raises(ValueError):
            derive_zhengwuxing_facts(
                mountain="乾", gans=["丁", "丁", "甲"], zhis=["未", "未"], month_zhi="未"
            )


def _assert_no_grade_fields(fx: dict) -> None:
    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            bad = {"grade", "verdict", "score", "weight", "severity"} & set(node)
            assert not bad, f"事实层出现档位字段 {bad} @ {path}"
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, (list, tuple)):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif node in {"大吉", "吉", "平", "凶", "大凶"}:
            raise AssertionError(f"事实层出现吉凶判断: {path} = {node!r}")

    walk({k: v for k, v in fx.items() if k != "note"}, "$")


class TestBulong:
    def test_sanhe_complete_and_month_office(self) -> None:
        fx = derive_bulong_facts(
            long_element="木",
            zhis=["亥", "卯", "未", "巳"],
            month_zhi="卯",
        )
        assert fx["long"]["sanhe_ju"] == ["亥", "卯", "未"]
        assert fx["sanhe_complete"] is True
        assert fx["month"]["sanhe_month"] is True
        assert fx["month"]["month_stage"] == "旺"
        assert fx["month"]["month_office"] == "临官"
        assert [s["step"] for s in fx["audit_chain"]] == [1, 2, 3]

    def test_incomplete_sanhe_is_false(self) -> None:
        fx = derive_bulong_facts(
            long_element="木",
            zhis=["亥", "卯", "酉", "丑"],
            month_zhi="酉",
        )
        assert fx["sanhe_complete"] is False
        assert fx["month"]["sanhe_month"] is False
        assert fx["month"]["month_office"] is None

    def test_tu_has_no_sanhe_and_no_office(self) -> None:
        """土无三合局，且土寄宫有异说——两者都必须显式为 None，不伪造。"""
        fx = derive_bulong_facts(
            long_element="土",
            zhis=["申", "子", "辰", "丑"],
            month_zhi="辰",
        )
        assert fx["long"]["sanhe_ju"] is None
        assert fx["sanhe_complete"] is False
        assert fx["month"]["sanhe_month"] is False
        assert fx["month"]["month_office"] is None
        assert "土寄宫" in fx["month"]["office_note"]

    def test_bulong_has_no_grade(self) -> None:
        fx = derive_bulong_facts(
            long_element="水", zhis=["申", "子", "辰", "寅"], month_zhi="子"
        )
        _assert_no_grade_fields(fx)
        assert fx["status"] == "待考证"
        assert "不判吉凶" in fx["note"]


class TestXiangzhu:
    def test_he_and_chong_are_reported(self) -> None:
        fx = derive_xiangzhu_facts(
            person_ganzhi="甲子",
            gans=["己", "庚", "丙", "丁"],
            zhis=["丑", "午", "寅", "酉"],
        )
        by_label = {p["label"]: p for p in fx["pillars"]}
        assert by_label["年"]["gan_he"] is True
        assert by_label["年"]["zhi_he"] is True
        assert by_label["月"]["zhi_chong"] is True
        assert by_label["月"]["gan_relation"] == "克入"
        assert fx["counts"] == {"gan_he": 1, "zhi_he": 1, "zhi_chong": 1}
        assert [s["step"] for s in fx["audit_chain"]] == [1, 2, 3, 4, 5, 6]

    def test_xiangzhu_has_no_grade(self) -> None:
        fx = derive_xiangzhu_facts(
            person_ganzhi="庚戌", gans=["丁", "丁", "甲", "己"], zhis=["未", "未", "午", "巳"]
        )
        _assert_no_grade_fields(fx)
        assert fx["status"] == "待考证"
        assert "不判吉凶" in fx["note"]

    def test_bad_person_ganzhi_rejected(self) -> None:
        with pytest.raises(ValueError):
            derive_xiangzhu_facts(person_ganzhi="甲", gans=["己"], zhis=["丑"])


class TestQ029NoGradeLock:
    """Q-029 未裁定前，正五行 facts 层不得被接成吉凶档位或投票规则。

    本仓库没有 ``EngineVerdict.grade`` 字段；等价的机器可读面是：
    - facts 里不得出现 grade/score/severity 等档位字段；
    - 规则 ``severity`` 不得取「大吉/吉/平/凶/大凶」；
    - 不得有规则以 ``facts.zhengwuxing.*`` 为条件（即不得把 facts 直接投票）。

    解锁唯一条件：``docs/rulings/q-029.yaml`` 存在、``decided: true``、
    ``signed_by`` 非空、``decision: A``（且 A 案须在文件内给出分值/档位界值）。
    B/C 案不产生档位，故仍执行本锁。
    """

    RULING = Path(__file__).resolve().parents[2] / "docs/rulings/q-029.yaml"
    GRADE_WORDS = {"大吉", "吉", "平", "凶", "大凶"}
    FORBIDDEN_KEYS = {"grade", "score", "severity", "verdict", "jixiong"}

    def _grades_allowed(self) -> bool:
        if not self.RULING.exists():
            return False
        import yaml

        ruling = yaml.safe_load(self.RULING.read_text(encoding="utf-8")) or {}
        assert ruling.get("decided") is True, "q-029.yaml 存在但 decided 不为 true"
        assert ruling.get("signed_by"), "q-029.yaml 缺人类签名 signed_by"
        assert ruling.get("decision") in {"A", "B", "C"}, "decision 只允许 A/B/C"
        if ruling["decision"] == "A":
            assert ruling.get("scores"), "A 案必须在裁定文件内给出分值表"
            assert ruling.get("grade_bounds"), "A 案必须给出档位界值"
        return ruling["decision"] == "A"

    def test_zhengwuxing_no_grade_without_q029_ruling(self) -> None:
        if self._grades_allowed():
            return
        from core_symbol.zhengwuxing import derive_zhengwuxing_facts

        fx = derive_zhengwuxing_facts(
            mountain="乾", gans=ACCEPT_GANS, zhis=ACCEPT_ZHIS, month_zhi=ACCEPT_MONTH_ZHI
        )

        def walk(node: object, path: str) -> None:
            if isinstance(node, dict):
                bad = self.FORBIDDEN_KEYS & set(node)
                assert not bad, f"Q-029 未裁定，facts 出现档位字段 {bad} @ {path}"
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, (list, tuple)):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
            elif node in self.GRADE_WORDS:
                raise AssertionError(f"Q-029 未裁定，facts 出现吉凶档位: {path} = {node!r}")

        walk({k: v for k, v in fx.items() if k != "note"}, "$")

    def test_no_rule_votes_on_zhengwuxing_facts_before_q029(self) -> None:
        if self._grades_allowed():
            return
        import yaml
        from core_rule.loader import load_ruleset

        root = Path(__file__).resolve().parents[2] / "core-rule/rules"
        for rule in load_ruleset(root).rules:
            dumped = yaml.safe_dump(rule.raw, allow_unicode=True)
            assert "facts.zhengwuxing" not in dumped, (
                f"{rule.rule_id} 在 Q-029 未裁定前引用了 facts.zhengwuxing"
            )
            assert "facts.xiangzhu" not in dumped, (
                f"{rule.rule_id} 在相主口径裁定前引用了 facts.xiangzhu"
            )
            if rule.school == "zhengwuxing":
                assert rule.severity not in self.GRADE_WORDS, rule.rule_id


class TestIntegration:
    def test_derive_facts_exposes_zhengwuxing(self) -> None:
        from datetime import date

        from core_symbol.mountain import mountain_by_name
        from core_symbol.registry import derive_facts

        mountain = mountain_by_name("乾")
        fx = derive_facts(
            year_zhi="未",
            month_zhi="未",
            day_ganzhi="甲午",
            gans=ACCEPT_GANS,
            zhis=ACCEPT_ZHIS,
            mountain=mountain,
            facing=mountain_by_name("巽"),
            shan_jia_zhi="亥",
            local_date=date(2027, 7, 11),
        )
        assert "zhengwuxing" in fx
        fushan = fx["zhengwuxing"]["fushan"]
        assert fushan["shan"] == {"name": "乾", "element": "金", "month_stage": "相"}
        assert len(fushan["pillars"]) == 4


def _base_facts():
    from datetime import date

    from core_symbol.mountain import mountain_by_name
    from core_symbol.registry import derive_facts

    return derive_facts(
        year_zhi="未",
        month_zhi="未",
        day_ganzhi="甲午",
        gans=ACCEPT_GANS,
        zhis=ACCEPT_ZHIS,
        mountain=mountain_by_name("乾"),
        facing=mountain_by_name("巽"),
        shan_jia_zhi="亥",
        local_date=date(2027, 7, 11),
    )


class TestOverlayWiring:
    """补龙/相主必须真的接在候选级 facts 上，而不是只存在于函数里。"""

    def _overlay(self, *, long_element=None, person_ganzhi=None):
        from core_symbol.registry import overlay_hour_facts

        return overlay_hour_facts(
            _base_facts(),
            gans=ACCEPT_GANS,
            zhis=ACCEPT_ZHIS,
            shan_jia_zhi="亥",
            day_ganzhi="甲午",
            month_zhi=ACCEPT_MONTH_ZHI,
            mountain_name="乾",
            doushou_tu_changsheng="shen",
            long_element=long_element,
            person_ganzhi=person_ganzhi,
        )

    def test_bulong_and_xiangzhu_present_when_inputs_given(self) -> None:
        fx = self._overlay(long_element="木", person_ganzhi="甲子")
        assert fx["zhengwuxing"]["bulong"]["long"]["sanhe_ju"] == ["亥", "卯", "未"]
        assert fx["xiangzhu"]["person"]["ganzhi"] == "甲子"
        assert len(fx["xiangzhu"]["pillars"]) == 4
        _assert_no_grade_fields(fx["zhengwuxing"]["bulong"])
        _assert_no_grade_fields(fx["xiangzhu"])

    def test_missing_inputs_are_explicit(self) -> None:
        fx = self._overlay()
        assert fx["zhengwuxing"]["bulong"]["status"] == "输入不足"
        assert fx["xiangzhu"]["status"] == "输入不足"
        assert "不判吉凶" in fx["zhengwuxing"]["bulong"]["note"]
        assert "不判吉凶" in fx["xiangzhu"]["note"]

    def test_fushan_is_recomputed_for_the_candidate_hour(self) -> None:
        """日级缓存不含时柱：overlay 必须用当前时柱重算扶山。"""
        from core_symbol.registry import overlay_hour_facts

        base = _base_facts()
        assert base["zhengwuxing"]["fushan"]["pillars"][3]["zhi"] == ACCEPT_ZHIS[3]
        other_zhis = ["未", "未", "午", "子"]
        fx = overlay_hour_facts(
            base,
            gans=ACCEPT_GANS,
            zhis=other_zhis,
            shan_jia_zhi="亥",
            day_ganzhi="甲午",
            month_zhi=ACCEPT_MONTH_ZHI,
            mountain_name="乾",
            doushou_tu_changsheng="shen",
        )
        assert fx["zhengwuxing"]["fushan"]["pillars"][3]["zhi"] == "子", (
            "扶山若沿用日级缓存，会把首个子时的时柱带给其他时辰"
        )


class TestInvalidInputsRejected:
    """非法输入必须报错，不能静默补齐或猜测。"""

    def test_non_element_rejected_by_month_stage(self) -> None:
        with pytest.raises(ValueError, match="非法五行"):
            month_stage_of("X", "子")

    def test_bulong_rejects_unknown_long_element(self) -> None:
        with pytest.raises(ValueError, match="非法入首龙五行"):
            derive_bulong_facts(long_element="X", zhis=["申", "子", "辰"], month_zhi="子")

    def test_bulong_rejects_unknown_zhi(self) -> None:
        with pytest.raises(ValueError, match="非法地支"):
            derive_bulong_facts(long_element="水", zhis=["申", "X"], month_zhi="子")

    def test_bulong_rejects_unknown_month_zhi(self) -> None:
        with pytest.raises(ValueError, match="非法月支"):
            derive_bulong_facts(long_element="水", zhis=["申"], month_zhi="X")

    def test_xiangzhu_rejects_person_ganzhi_with_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="主命干支必须是两字"):
            derive_xiangzhu_facts(person_ganzhi="庚", gans=["甲"], zhis=["子"])
        with pytest.raises(ValueError, match="主命干支必须是两字"):
            derive_xiangzhu_facts(person_ganzhi=None, gans=["甲"], zhis=["子"])  # type: ignore[arg-type]

    def test_xiangzhu_rejects_pillar_count_mismatch(self) -> None:
        with pytest.raises(ValueError, match="数量不一致"):
            derive_xiangzhu_facts(person_ganzhi="庚戌", gans=["甲", "乙"], zhis=["子"])

    def test_xiangzhu_rejects_unknown_person_ganzhi(self) -> None:
        with pytest.raises(ValueError, match="非法主命干支"):
            derive_xiangzhu_facts(person_ganzhi="X子", gans=["甲"], zhis=["子"])

    def test_xiangzhu_rejects_unknown_pillar_ganzhi(self) -> None:
        with pytest.raises(ValueError, match="非法干支"):
            derive_xiangzhu_facts(person_ganzhi="庚戌", gans=["甲"], zhis=["X"])


class TestTableInvariants:
    """导入期表校验必须真的能拦住破坏，而不是永远为真。"""

    def test_missing_mountain_rejected(self, monkeypatch) -> None:
        from core_symbol import zhengwuxing as zw

        broken = dict(zw.SHAN_WUXING_24)
        broken.pop(next(iter(broken)))
        monkeypatch.setattr(zw, "SHAN_WUXING_24", broken)
        with pytest.raises(RuntimeError, match="二十四山正五行表未覆盖"):
            zw._validate_tables()

    def test_illegal_mountain_element_rejected(self, monkeypatch) -> None:
        from core_symbol import zhengwuxing as zw

        broken = dict(zw.SHAN_WUXING_24)
        broken[next(iter(broken))] = "X"
        monkeypatch.setattr(zw, "SHAN_WUXING_24", broken)
        with pytest.raises(RuntimeError, match="含非法五行"):
            zw._validate_tables()

    def test_incomplete_sheng_ke_rejected(self, monkeypatch) -> None:
        from core_symbol import zhengwuxing as zw

        monkeypatch.setattr(zw, "SHENG", {"木": "火"})
        with pytest.raises(RuntimeError, match="生克表未覆盖五行"):
            zw._validate_tables()

    def test_illegal_sanhe_element_rejected(self, monkeypatch) -> None:
        from core_symbol import zhengwuxing as zw

        broken = dict(zw.SANHE_JU)
        broken["X"] = ("申", "子", "辰")
        monkeypatch.setattr(zw, "SANHE_JU", broken)
        with pytest.raises(RuntimeError, match="三合局表含非法五行"):
            zw._validate_tables()

    def test_gan_he_must_cover_ten_stems(self, monkeypatch) -> None:
        from core_symbol import zhengwuxing as zw

        monkeypatch.setattr(zw, "GAN_HE", {"甲": "己"})
        with pytest.raises(RuntimeError, match="天干五合表未覆盖十干"):
            zw._validate_tables()

    def test_zhi_tables_must_cover_twelve_branches(self, monkeypatch) -> None:
        from core_symbol import zhengwuxing as zw

        monkeypatch.setattr(zw, "ZHI_HE", {"子": "丑"})
        with pytest.raises(RuntimeError, match="地支六合／六冲表未覆盖十二支"):
            zw._validate_tables()
