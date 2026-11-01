"""天星 facts（Phase 8 收尾）：七政四余真星历（pyswisseph/Moshier）+ 到山到向 + 三合照 + 升殿。

**须真实星历，禁查表近似**（spec §2.5）。星历用 pyswisseph（Moshier 无需数据文件，
精度对日月五星 ≈ 0.1″ 量级）；库未安装时全部事实降级为 ``None``（unknown），
绝不以近似表替代——由规则层 unknown 语义兜底，不静默给 False。

口径清单（全部显式声明，``needs_human_review`` 挂流派分歧）
------------------------------------------------------------
1. **到山制式**：黄道制——黄经 L 对应方位角 ``(L+90) mod 360``，即二十四节气
   太阳到山表（协纪辨方书系）：冬至太阳到子、春分到卯、夏至到午、秋分到酉、
   立春到艮、立夏到巽、立秋到坤、立冬到乾。赤道制另说 → needs_human_review。
2. **用时刻**：用事日**北京正午**（UTC+8 12:00 → UT 04:00）取星象；
   逐时刻精确取用事时辰属需求/流派分歧 → needs_human_review。
3. **二十八宿**：不等宽宿度表（``tianxing_28xiu.json``，传统 365.25 度制）；
   角宿距星锚点取角宿一（Spica）J2000 黄经 203.84°，按岁差 50.3″/年东移
   校正到用事年份。距度体系（开禧/时宪）另说 → needs_human_review。
   **实测数据问题**：表内距度总和 364 < 365.25，表末 1.25 度区间无宿可归——
   星曜落入该区间时宿位输出 ``None`` 并注记，不做均摊/归一化处理。
4. **升殿**：曜在其本曜之宿（日=房虚昴星、月=心危毕张，五星在同行之宿）；
   宿曜属性行取自宿度表 ``element`` 字段。四余为暗曜不升殿（古典通说）。
4a. **日月夹辅**（spec §2.5 关键吉格）：太阳与太阴分居目标（坐山/向山）
   两侧**相邻山**（罗盘序 ±1）→ 夹辅成立；只取相邻一山的窄夹，
   宽夹（±2/三合夹）他派另说 → needs_human_review。
5. **三合照**：太阳/太阴居坐山三合之位（如坐子，日在申或辰）；仅十二支山
   可判——八干四维山的纳甲/挨星归属属流派分歧 → 输出 ``None``。
6. **四余**：罗睺=平交点（swisseph MEAN_NODE）、计都=罗睺+180°、月孛=月远地点
   （SE_MEAN_APOG）；**紫气**无现代天文对应且传统推算口径未裁定 → 不推算，
   整组事实标 ``completeness: PARTIAL``（spec §2.5 允许）。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .mountain import MOUNTAINS_24

__all__ = [
    "SWE_AVAILABLE",
    "shan_of_longitude",
    "xiu_of_longitude",
    "derive_tianxing_facts",
]

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "core-rule" / "config" / "data"

try:  # 星历库为可选依赖：缺失时事实降级 unknown，不近似
    import swisseph as _swe

    SWE_AVAILABLE = True
except ImportError:  # pragma: no cover - 环境相关
    _swe = None
    SWE_AVAILABLE = False

#: 天体 → swisseph 体号（紫气无对应 → None）
_BODIES: tuple[tuple[str, int | None], ...] = (
    ("日", _swe.SUN if SWE_AVAILABLE else None),
    ("月", _swe.MOON if SWE_AVAILABLE else None),
    ("水", _swe.MERCURY if SWE_AVAILABLE else None),
    ("金", _swe.VENUS if SWE_AVAILABLE else None),
    ("火", _swe.MARS if SWE_AVAILABLE else None),
    ("木", _swe.JUPITER if SWE_AVAILABLE else None),
    ("土", _swe.SATURN if SWE_AVAILABLE else None),
    ("罗睺", _swe.MEAN_NODE if SWE_AVAILABLE else None),
    ("月孛", _swe.MEAN_APOG if SWE_AVAILABLE else None),
)

#: 七政曜星 → 本曜（升殿判定用；四余不升殿）
_QIZHENG_ELEMENT = {"日": "日", "月": "月", "木": "木", "火": "火", "土": "土", "金": "金", "水": "水"}

#: 十二支山三合局（天星三合照用；八干四维山不判）
_SANHE_OF_ZHI = {
    "子": ("申", "辰"), "丑": ("巳", "酉"), "寅": ("午", "戌"), "卯": ("未", "亥"),
    "辰": ("申", "子"), "巳": ("酉", "丑"), "午": ("寅", "戌"), "未": ("亥", "卯"),
    "申": ("子", "辰"), "酉": ("巳", "丑"), "戌": ("午", "寅"), "亥": ("卯", "未"),
}

#: 角宿距星（角宿一 Spica）J2000 黄道经度（现代天文值）与岁差速率
_J2000_JIAO_LONGITUDE = 203.84
_PRECESSION_ARCSEC_PER_YEAR = 50.3
_TRAD_PER_MODERN = 365.25 / 360.0  # 传统度（365.25 度/周天）较现代度大，1 现代度 = 1.0146 传统度


# C19-exempt: 单一不可变参数（进程常量数据/日历换算），键由解释器按参数构造，无复合串味面
@lru_cache(maxsize=1)
def _load_28xiu() -> dict[str, Any]:
    return json.loads((_DATA_DIR / "tianxing_28xiu.json").read_text(encoding="utf-8"))


def shan_of_longitude(longitude: float) -> str:
    """黄道经度 → 二十四山（黄道制：L → 方位角 (L+90)%360 → 山）。

    锚定（协纪辨方书系太阳到山表）：冬至（黄经 270°）到子、春分（0°）到卯、
    夏至（90°）到午、秋分（180°）到酉、四立到四维。
    """
    bearing = (longitude + 90.0) % 360.0
    return MOUNTAINS_24[int(bearing // 15)]


def jiao_start_longitude(year: int) -> float:
    """用事年份的角宿起点黄经（岁差校正）。"""
    return (_J2000_JIAO_LONGITUDE + _PRECESSION_ARCSEC_PER_YEAR / 3600.0 * (year - 2000)) % 360.0


def xiu_of_longitude(longitude: float, year: int) -> dict[str, Any]:
    """黄道经度 → 二十八宿位（不等宽宿度 + 岁差，禁 360/28 均分）。

    返回 ``{xiu, ruxiu_du, element}``；星曜落在表末残差区间
    （距度总和 364 < 365.25）时 ``xiu`` 为 ``None`` 并注记——不均摊。
    """
    xiu_list = _load_28xiu()["xiu"]
    offset_modern = (longitude - jiao_start_longitude(year)) % 360.0
    offset_trad = offset_modern * _TRAD_PER_MODERN  # 现代度 → 传统度
    acc = 0.0
    for x in xiu_list:
        w = float(x["xiu_width"])
        if offset_trad < acc + w:
            return {"xiu": x["name"], "ruxiu_du": round(offset_trad - acc, 4), "element": x["element"]}
        acc += w
    return {
        "xiu": None,
        "ruxiu_du": round(offset_trad - acc, 4),
        "element": None,
        "note": "落宿度表末残差区间（总和 364 < 365.25，1.25 度无宿可归）",
    }


def _noon_ut_julday(year: int, month: int, day: int) -> float:
    """用事日北京正午（UTC+8 12:00 = UT 04:00）的儒略日。"""
    assert _swe is not None
    return _swe.julday(year, month, day, 4.0)


# C19-exempt: 单一不可变参数（进程常量数据/日历换算），键由解释器按参数构造，无复合串味面
@lru_cache(maxsize=4096)
def _positions(year: int, month: int, day: int) -> dict[str, Any]:
    """七政四余黄道经度（Moshier，无数据文件依赖）。

    按日期缓存：口径为**用事日北京正午**取象（见模块头口径 2），同日各时辰
    候选共享同一星象——全年 4380 候选只需 ~365×9 次 calc_ut，而非逐候选计算
    （曾致 perf 基线 1.9s → 3.8s 回归）。返回值只读，调用方不得修改。
    """
    assert _swe is not None
    jd = _noon_ut_julday(year, month, day)
    out: dict[str, Any] = {}
    for name, pid in _BODIES:
        if pid is None:
            out[name] = {"longitude": None, "note": "无星历体对应"}
            continue
        pos, _ = _swe.calc_ut(jd, pid, _swe.FLG_MOSEPH)
        lon = pos[0] % 360.0
        out[name] = {"longitude": round(lon, 6)}
    # 计都 = 罗睺 + 180°
    luo = out["罗睺"]["longitude"]
    out["计都"] = {"longitude": None if luo is None else round((luo + 180.0) % 360.0, 6)}
    # 紫气：无现代天文对应，不推算（spec §2.5 允许 PARTIAL）
    out["紫气"] = {"longitude": None, "note": "传统隐曜，推算口径未裁定——不推算"}
    return out


def derive_tianxing_facts(
    *,
    mountain_name: str,
    facing_name: str | None,
    local_date: Any | None,
) -> dict[str, Any]:
    """展开 ``facts.tianxing.*``（结构事实 + 到山比对，无吉凶断语）。"""
    base_review = [
        "到山制式：黄道制（协纪节气到山表锚定）vs 赤道制两说",
        "用时刻：北京正午 vs 用事时辰逐时刻",
        "角宿距星锚点（角宿一 J2000 黄经 203.84°）与距度体系（开禧/时宪）",
        "二十八宿距度表总和 364 < 365.25，表末 1.25 度无宿可归；数据源 unverified",
        "三合照仅十二支山可判——八干四维山纳甲/挨星归属分歧",
    ]
    if not SWE_AVAILABLE:
        return {
            "sun_daoshan": None, "moon_daoshan": None,
            "sanhe_gongzhao": None, "jiafu": None,
            "riyue_jiafu": None,
            "bodies": None,
            "completeness": "PARTIAL",
            "missing": ["pyswisseph 未安装——全部天星事实降级 unknown，不以近似表替代"],
            "caliber": {"note": "星历库缺失，未计算"},
            "needs_human_review": base_review,
            "status": "待考证",
        }
    if local_date is None:
        return {
            "sun_daoshan": None, "moon_daoshan": None,
            "sanhe_gongzhao": None, "jiafu": None,
            "riyue_jiafu": None,
            "bodies": None,
            "completeness": "PARTIAL",
            "missing": ["缺少用事日期，无法取星象"],
            "caliber": {"note": "缺少用事日期，未计算"},
            "needs_human_review": base_review,
            "status": "待考证",
        }

    year = local_date.year
    pos = _positions(year, local_date.month, local_date.day)

    bodies: dict[str, Any] = {}
    for name, info in pos.items():
        lon = info["longitude"]
        entry: dict[str, Any] = {"longitude": lon, "shan": None, "xiu": None, "shengdian": None}
        if lon is not None:
            entry["shan"] = shan_of_longitude(lon)
            xiu_info = xiu_of_longitude(lon, year)
            entry["xiu"] = xiu_info["xiu"]
            entry["ruxiu_du"] = xiu_info["ruxiu_du"]
            if name in _QIZHENG_ELEMENT and xiu_info["xiu"] is not None:
                entry["shengdian"] = xiu_info["element"] == _QIZHENG_ELEMENT[name]
        bodies[name] = entry

    sun, moon = bodies["日"], bodies["月"]
    sun_daoshan = None if sun["shan"] is None else sun["shan"] == mountain_name
    moon_daoshan = None if moon["shan"] is None else moon["shan"] == mountain_name
    sun_daoxiang = None
    moon_daoxiang = None
    if facing_name is not None:
        sun_daoxiang = None if sun["shan"] is None else sun["shan"] == facing_name
        moon_daoxiang = None if moon["shan"] is None else moon["shan"] == facing_name

    # 三合照：仅十二支山；日月居坐山三合之位
    sanhe_gongzhao: bool | None = None
    if mountain_name in _SANHE_OF_ZHI:
        trio = _SANHE_OF_ZHI[mountain_name]
        shans = {sun["shan"], moon["shan"]}
        if None not in shans:
            sanhe_gongzhao = bool(shans & set(trio))

    # 七政到坐山且升殿（四余不升殿，不参与）
    jiafu = any(
        bodies[n]["shan"] == mountain_name and bodies[n]["shengdian"]
        for n in _QIZHENG_ELEMENT
        if bodies[n]["shan"] is not None
    )

    # 日月夹辅（spec §2.5 关键吉格）：日月分居目标两侧相邻山（罗盘序 ±1）
    def _jia_fu(target: str | None) -> bool | None:
        if target is None or sun["shan"] is None or moon["shan"] is None:
            return None
        ti = MOUNTAINS_24.index(target)
        si, mi = MOUNTAINS_24.index(sun["shan"]), MOUNTAINS_24.index(moon["shan"])
        return {si, mi} == {(ti - 1) % 24, (ti + 1) % 24}

    riyue_jiafu = {"shan": _jia_fu(mountain_name), "xiang": _jia_fu(facing_name)}

    return {
        "sun_daoshan": sun_daoshan,
        "moon_daoshan": moon_daoshan,
        "sun_daoxiang": sun_daoxiang,
        "moon_daoxiang": moon_daoxiang,
        "sanhe_gongzhao": sanhe_gongzhao,
        "jiafu": jiafu,
        "riyue_jiafu": riyue_jiafu,
        "bodies": bodies,
        "completeness": "PARTIAL",
        "missing": ["紫气（传统隐曜，推算口径未裁定——不推算）"],
        "caliber": {
            "frame": "黄道制（L→方位角 (L+90)%360；冬至太阳到子、春分到卯）",
            "moment": "用事日北京正午（UT 04:00）",
            "xiu_anchor": "角宿距星=角宿一 J2000 黄经 203.84°，岁差 50.3″/年",
            "shengdian": "曜在本曜之宿（日房虚昴星/月心危毕张/五星同行之宿）；四余不升殿",
            "jiafu_riyue": "日月分居目标两侧相邻山（罗盘序 ±1）为夹辅；宽夹他派另说",
            "ephemeris": "pyswisseph Moshier（无数据文件），禁查表近似",
        },
        "needs_human_review": base_review,
        "status": "待考证",
    }
