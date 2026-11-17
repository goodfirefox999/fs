"""T5 罗盘抽取：§5.4 全部 11 条真值 + 边界用例。文档验收硬门槛。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extract_bearing import (  # noqa: E402
    SHAN24,
    SHAN_CENTER,
    angular_delta,
    degree_to_shan,
    extract_bearings,
    validate,
)

TRUTHS = [
    # (原文, label, shan, deg, offset, consistent, boundary_risk, needs_review)
    ("碑坐寅山66度", "碑坐", "寅", 66.0, 6.0, True, False, False),
    ("星顶：艮52度", "星顶", "艮", 52.0, 7.0, True, True, False),
    ("朝山：申246度", "朝山", "申", 246.0, 6.0, True, False, False),
    ("左峰：巳151度", "左峰", "巳", 151.0, 1.0, True, False, False),
    ("倒戈山酉275度", "倒戈山", "酉", 275.0, 5.0, True, False, False),
    ("其它峰酉263度", "其它峰", "酉", 263.0, -7.0, True, True, False),
    ("辛288度", "", "辛", 288.0, 3.0, True, False, True),   # 空 label 无法归类 → needs_review
    ("御屏亥328度", "御屏", "亥", 328.0, -2.0, True, False, False),
    ("内水口出：酉266度", "内水口出", "酉", 266.0, -4.0, True, False, False),
    ("碑坐甲山71度", "碑坐", "甲", 71.0, -4.0, True, False, False),
    ("外方河水来见于辛283度", "外方河水来见于", "辛", 283.0, -2.0, True, False, False),
]


def test_shan24_table() -> None:
    assert len(SHAN24) == 24
    assert len(SHAN_CENTER) == 24
    assert SHAN_CENTER["子"] == 0.0
    assert SHAN_CENTER["午"] == 180.0
    assert SHAN_CENTER["酉"] == 270.0


def test_truth_table() -> None:
    for raw, label, shan, deg, offset, consistent, boundary, review in TRUTHS:
        obs = extract_bearings(raw)
        assert len(obs) == 1, f"{raw}: 期望1条观测，得到 {[(o.label, o.shan24, o.degree) for o in obs]}"
        o = obs[0]
        assert o.label == label, f"{raw}: label={o.label!r} 期望 {label!r}"
        assert o.shan24 == shan, f"{raw}: shan={o.shan24} 期望 {shan}"
        assert o.degree == deg, f"{raw}: deg={o.degree}"
        assert o.offset_from_center == offset, f"{raw}: offset={o.offset_from_center} 期望 {offset}"
        assert o.is_consistent is consistent, f"{raw}: consistent={o.is_consistent}"
        assert o.is_boundary_risk is boundary, f"{raw}: boundary={o.is_boundary_risk} 期望 {boundary}"
        assert o.needs_review is review, f"{raw}: needs_review={o.needs_review} 期望 {review}"


def test_extract_context_sequence() -> None:
    """连续文本：标签承接上文 + 不串位。"""
    text = "倒戈山酉275度，辛288度。御屏亥328度。"
    obs = extract_bearings(text)
    pairs = [(o.label, o.shan24, o.degree) for o in obs]
    assert ("倒戈山", "酉", 275.0) in pairs
    assert ("御屏", "亥", 328.0) in pairs
    assert any(s == "辛" and d == 288.0 for _, s, d in pairs)


def test_boundary_degrees() -> None:
    # 0 度 = 子
    assert degree_to_shan(0.0) == "子"
    # 359.9 度 → 子（352.5~7.5 属子）
    assert degree_to_shan(359.9) == "子"
    # 骑线：22.5 度是子/癸山界——以癸（中心15）为参照时距界 7.5
    obs = validate("测试", "癸", 22.5)
    assert obs.is_boundary_risk is True
    # 卦界：45 度正对四维卦界（文档 gua 公式直接按度数判定）
    obs = validate("测试", "艮", 45.0)
    assert obs.is_gua_boundary_risk is True
    # 山名参照与度数差 180 时 angular_delta 返回 -180（文档公式语义）
    assert angular_delta(180.0, 0.0) == -180.0


def test_shan_degree_conflict() -> None:
    """山名与度数矛盾 → 保留 + needs_review（禁止丢弃）。"""
    obs = validate("矛盾测试", "子", 180.0)  # 子=0，180=午
    assert obs.is_consistent is False
    assert obs.needs_review is True
    assert obs.shan24 == "子"


def test_deg_only_fallback() -> None:
    obs = extract_bearings("水口方向246度")
    assert len(obs) == 1
    o = obs[0]
    assert o.shan24 is None
    assert o.degree == 246.0
    assert o.shan_from_degree == "申"
    assert o.is_consistent is True  # 由度数反推必然自洽


def test_angular_delta() -> None:
    assert angular_delta(10, 350) == 20.0
    assert angular_delta(350, 10) == -20.0
    assert angular_delta(180, 0) == -180.0  # 文档公式在 ±180 处取 -180


def test_category() -> None:
    assert validate("碑坐", "寅", 66.0).category == "坐向"
    assert validate("星顶", "艮", 52.0).category == "来龙"
    assert validate("朝山", "申", 246.0).category == "砂峰"
    assert validate("外方河水来见于", "辛", 283.0).category == "来水"
    assert validate("内水口出", "酉", 266.0).category == "去水"


# ---------- 非周天度的排除（2026-11-02 补） ----------

def test_jianxiang_offset_is_not_bearing() -> None:
    """「丙山壬向兼巳亥5度」的 5 度是兼的偏移，不是周天度，不能入库当坐向。"""
    st: dict[str, int] = {}
    obs = extract_bearings("坟立丙山壬向兼巳亥5度", st)
    assert obs == []
    assert st["skipped_jianxiang"] == 1


def test_jianxiang_does_not_swallow_real_bearing() -> None:
    """同一句里兼向后面的真方位不能被连坐。"""
    st: dict[str, int] = {}
    obs = extract_bearings("立丙山壬向兼巳亥5度，朝山申246度", st)
    assert len(obs) == 1
    assert (obs[0].label, obs[0].shan24, obs[0].degree) == ("朝山", "申", 246.0)
    assert obs[0].category == "砂峰"
    assert st["skipped_jianxiang"] == 1


def test_astro_longitude_is_not_bearing() -> None:
    """七政四余的缠度（日寅24度 / 金寅18度 / 天王亥22度）不是实地方位。"""
    st: dict[str, int] = {}
    obs = extract_bearings("，日寅24度 月寅24度 金寅18度 土辰3度 天王亥22度", st)
    assert obs == []
    assert st["skipped_astro"] == 5


def test_zhoutian_label_survives() -> None:
    """「周天」是真方位词，不能被星曜判据误杀。"""
    obs = extract_bearings("水口于周天297度")
    assert len(obs) == 1 and obs[0].degree == 297.0
    assert obs[0].category == "去水"
