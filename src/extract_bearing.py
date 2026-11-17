"""罗盘度数抽取与二十四山校验（文档 T5 ★ 核心模块）。

验收：§5.4 的 11 条真值测试必须全部通过（见 tests/test_bearing.py）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SHAN24: list[str] = [
    "子", "癸", "丑", "艮", "寅", "甲", "卯", "乙", "辰", "巽", "巳", "丙",
    "午", "丁", "未", "坤", "申", "庚", "酉", "辛", "戌", "乾", "亥", "壬",
]
SHAN_CENTER: dict[str, float] = {s: i * 15.0 for i, s in enumerate(SHAN24)}
SHAN_HALF_WIDTH: float = 7.5

SHAN_CHARS = "".join(SHAN24)
# 主模式：前置描述词 + 山名（可带「山」字）+ 度数
# label 类含全角冒号/顿号等（实测「星顶：艮52度」「内水口出：酉266度」），尾部标点在 validate 中剥离
BEARING_PAT = re.compile(
    rf"(?P<label>[\u4e00-\u9fa5A-Za-z0-9：:，,、。；;]{{0,14}}?)"
    rf"\s*(?P<shan>[{SHAN_CHARS}]山?)"
    rf"\s*(?P<deg>\d{{1,3}}(?:\.\d+)?)\s*度"
)
# 补充模式：仅有度数无山名 → 由度数反推所属山
DEG_ONLY_PAT = re.compile(r"(?P<label>[\u4e00-\u9fa5]{0,14}?)\s*(?P<deg>\d{1,3}(?:\.\d+)?)\s*度")

BEARING_CATEGORY: dict[str, list[str]] = {
    "坐向": ["碑坐", "坐", "立向", "山向", "分金"],
    "来龙": ["星顶", "来龙", "入首", "祖山", "父母山", "过峡"],
    "砂峰": ["朝山", "案山", "左峰", "右峰", "御屏", "倒戈山", "峰", "砂", "青龙", "白虎", "曜星"],
    "来水": ["水来", "来水", "逆水", "河水来", "见水"],
    "去水": ["水口", "出水", "内水口", "外水口", "水出", "去水"],
}


@dataclass
class BearingObservation:
    label: str
    shan24: str | None          # 文本给出的山名（DEG_ONLY 时为 None）
    degree: float
    shan_from_degree: str
    offset_from_center: float
    is_consistent: bool
    is_boundary_risk: bool
    is_gua_boundary_risk: bool
    category: str = "UNCLASSIFIED"
    raw_text: str = ""
    needs_review: bool = False


def angular_delta(a: float, b: float) -> float:
    """有符号最小角差，范围 (-180, 180]。"""
    return (a - b + 180.0) % 360.0 - 180.0


def degree_to_shan(deg: float) -> str:
    """由度数反推二十四山（含骑线判定：+7.5 偏移取整）。"""
    idx = int(((deg + 7.5) % 360.0) // 15)
    return SHAN24[idx]


def validate(label: str, shan_text: str | None, deg: float) -> BearingObservation:
    """按文档 §5.3 校验逻辑构造观测值。"""
    shan = (shan_text or "").rstrip("山") or None
    if shan is not None:
        center = SHAN_CENTER[shan]
    else:
        center = SHAN_CENTER[degree_to_shan(deg)]
    delta = angular_delta(deg, center)
    consistent = abs(delta) <= SHAN_HALF_WIDTH
    boundary = abs(abs(delta) - SHAN_HALF_WIDTH) <= 1.0
    gua_boundary = abs(abs((deg + 22.5) % 45.0) - 22.5) <= 1.0
    obs = BearingObservation(
        label=label.strip(" ：:，,、。；;"),
        shan24=shan,
        degree=float(deg),
        shan_from_degree=degree_to_shan(deg),
        offset_from_center=round(delta, 2),
        is_consistent=consistent,
        is_boundary_risk=boundary,
        is_gua_boundary_risk=gua_boundary,
        raw_text=f"{label}{shan or ''}{deg}度",
    )
    obs.category = classify(obs)
    # 矛盾：文本山名与度数反推不一致 → 保留并标记（禁止丢弃）
    if shan is not None and shan != degree_to_shan(deg):
        obs.needs_review = True
    if obs.category == "UNCLASSIFIED":
        obs.needs_review = True
    return obs


def classify(obs: BearingObservation) -> str:
    """按 label 前缀词归类（文档 §5.5）。"""
    label = obs.label
    if not label:
        return "UNCLASSIFIED"
    for category, prefixes in BEARING_CATEGORY.items():
        for p in prefixes:
            if p in label:
                return category
    return "UNCLASSIFIED"


# ---------- 非周天度的排除 ----------
# 这两类在语料里大量出现，字面都是"某山+数字+度"，但都不是罗盘周天度，
# 硬当方位入库会污染最关键的「坐向」类（实测 1,290 条里 820 条归不了类、
# 642 条要人工复核，主因就是它们）。
_CELESTIAL = "日月金木水火土"
_ASTRO_PREFIX = ("天王", "海王", "冥王")


def _is_astro_label(label: str) -> bool:
    """七政四余的"缠度"：日寅24度 / 月寅24度 / 金寅18度 / 天王亥22度。

    判据只看 label 本身：星曜名恰好是 1~2 字且以七政之一收尾。
    「周天」「某方」这类真方位词一律排除，避免"水口于周天297度"被误伤。
    """
    lb = label.strip(" ：:，,、。；;")
    if not lb or "周天" in lb:
        return False
    if any(lb.endswith(p) for p in _ASTRO_PREFIX):
        return True
    return len(lb) <= 2 and lb[-1] in _CELESTIAL


def _is_jianxiang(text: str, shan_start: int) -> bool:
    """兼向度数：丙山壬向兼巳亥5度 —— 这个 5 度是兼的偏移，不是周天度。

    只在山名往前 12 字内找"兼"，且"兼"之后不能跨句读，避免把
    「…兼巳亥5度，朝山申246度」里的真方位一起误杀。
    """
    win = text[max(0, shan_start - 12):shan_start]
    i = win.rfind("兼")
    if i < 0:
        return False
    return not any(p in win[i:] for p in "，,。；;")


def extract_bearings(text: str, stats: dict[str, int] | None = None) -> list[BearingObservation]:
    """从文本抽取全部罗盘观测值。

    BEARING_PAT 优先；DEG_ONLY_PAT 仅补充未覆盖的度数片段（span 去重）。
    兼向偏移与七政缠度不是周天度，直接跳过（原文仍在 content_clean 里，可回溯）。
    """
    out: list[BearingObservation] = []
    consumed: list[tuple[int, int]] = []
    skipped_jx = skipped_astro = 0
    for m in BEARING_PAT.finditer(text):
        label = m.group("label") or ""
        shan = m.group("shan")
        deg = float(m.group("deg"))
        if deg > 360:
            continue
        if _is_jianxiang(text, m.start("shan")):
            skipped_jx += 1
            consumed.append(m.span())      # 跳过也要占位，否则 DEG_ONLY 会把同一段再捞回来
            continue
        if _is_astro_label(label):
            skipped_astro += 1
            consumed.append(m.span())
            continue
        obs = validate(label, shan, deg)
        obs.raw_text = m.group(0)
        out.append(obs)
        consumed.append(m.span())
    for m in DEG_ONLY_PAT.finditer(text):
        if any(s <= m.start() < e for s, e in consumed):
            continue
        deg = float(m.group("deg"))
        if deg > 360:
            continue
        if _is_astro_label(m.group("label") or ""):
            skipped_astro += 1
            consumed.append(m.span())
            continue
        obs = validate(m.group("label") or "", None, deg)
        obs.raw_text = m.group(0)
        out.append(obs)
        consumed.append(m.span())
    if stats is not None:
        stats["skipped_jianxiang"] = skipped_jx
        stats["skipped_astro"] = skipped_astro
    return out
