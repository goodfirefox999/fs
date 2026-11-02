"""输入/输出模型与上下文构建（应用层）。

本层职责是**组合**：把 ``core-time`` 的四柱与 ``core-symbol`` 的派生事实组装成
``core-eval`` 需要的 ctx。**不写任何计算逻辑**（铁律：应用层只组合，不写计算）。

输入三对象（Person / Site / Task）字段对齐 docs/DEVELOPMENT.md 第 4.1 节。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from core_rule.calibers import (
    CALIBER_DOUSHO,
    CALIBER_JIANXIANG,
    CALIBER_NAYIN,
    CALIBER_SANSHA,
    CALIBER_TIANDE_GUA,
    CALIBER_ZIBAI_FLY,
    CaliberRegistry,
    load_caliber_sets,
)
from core_symbol.ganzhi import ZHI
from core_symbol.mountain import Mountain, facing_of, fenjin_of_azimuth, jian_xiang, mountain_of_azimuth
from core_symbol.registry import derive_facts, overlay_hour_facts
from core_time import CalendarConfig, compute_four_pillars, terms_of_year
from core_time.hashing import stable_cache_key  # C19：统一缓存键

#: 日级事实缓存：只存**与时辰无关**的部分（节气/三煞/五黄/玄空/天星/董公/调候…）。
#:
#: 历史 bug（2026-11-02 修复，两阶段）：此处曾整包按日缓存，理由是
#: "derive_facts 无时辰参数"——该前提是错的。``derive_facts`` 收到的 ``gans``/``zhis``
#: 是四柱（含时柱），``facts.structure``（刑冲害破合/重复计数/三合局）、
#: ``facts.xunkong.hits``、``facts.tongguan``、``facts.sanhe_ju``、``facts.doushou``
#: 都随时支变化。整包按日缓存 → 同日子时先算出的事实被其余 11 个时辰复用，
#: 表现为「14:00 的日课拿到 00:00 的刑害关系」；生成器 tier 按当日首个子时计，
#: 且暴力对照测试因走同一缓存而"一致通过"（假阴性）。
#: 第一版修复是整包按候选缓存（键含时柱），正确但把 derive_facts 从 365 次变成
#: 4380 次（实测 2.7s→5.4s，超 3s 预算）。现改为：日级缓存 + ``overlay_hour_facts``
#: 逐候选重算时变部分，正确性与预算兼得。
#: 超上限整表清空（候选按时间顺序生成，清空只损失复用）。
_FACTS_CACHE: dict[tuple, dict[str, Any]] = {}
_FACTS_CACHE_MAX = 8192

__all__ = [
    "PersonSpec",
    "SiteSpec",
    "TaskSpec",
    "CourseSpec",
    "build_context",
    "EVALUATION_SCHEMA",
    "validate_schema",
    "MINIMAL_SCHEMA_VALIDATOR",
]


@dataclass(frozen=True)
class PersonSpec:
    """命主。所有字段可选 —— 缺失时相关规则降级为 unknown（输入不足），不得静默通过。"""

    name: str | None = None
    birth_dt: datetime | None = None
    birth_lon: float | None = None
    birth_lat: float | None = None
    gender: str | None = None
    year_zhi: str | None = None  # 人工覆盖
    year_gz: str | None = None
    lunar_override: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "birth_dt": self.birth_dt.isoformat() if self.birth_dt else None,
            "birth_lon": self.birth_lon,
            "birth_lat": self.birth_lat,
            "gender": self.gender,
            "year_zhi": self.year_zhi,
            "year_gz": self.year_gz,
            "lunar_override": self.lunar_override,
        }

    @property
    def provided(self) -> bool:
        return bool(self.year_zhi or self.year_gz or self.birth_dt)


@dataclass(frozen=True)
class SiteSpec:
    """地点与坐向。``azimuth_deg`` 为实测罗盘方位角。"""

    azimuth_deg: float
    lat: float = 0.0
    lon: float | None = None
    mountain: str | None = None
    facing: str | None = None
    fenjin: str | None = None
    measure_method: str = "unspecified"
    angle_uncertainty_deg: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "azimuth_deg": self.azimuth_deg,
            "lat": self.lat,
            "lon": self.lon,
            "mountain": self.mountain,
            "facing": self.facing,
            "fenjin": self.fenjin,
            "measure_method": self.measure_method,
            "angle_uncertainty_deg": self.angle_uncertainty_deg,
        }


@dataclass(frozen=True)
class TaskSpec:
    """事项。"""

    kind: str
    nodes: tuple[str, ...] = ()
    strictness: str = "normal"
    granularity: str = "day_hour"
    extra_constraints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "nodes": list(self.nodes),
            "strictness": self.strictness,
            "granularity": self.granularity,
            "extra_constraints": dict(self.extra_constraints),
        }


@dataclass(frozen=True)
class CourseSpec:
    """一个日课候选（年月日时）。"""

    dt: datetime
    node: str | None = None


# C19-exempt: 单一不可变参数（进程常量数据/日历换算），键由解释器按参数构造，无复合串味面
@lru_cache(maxsize=512)
# C19-exempt: 单一不可变参数（进程常量数据/日历换算），键由解释器按参数构造，无复合串味面
@lru_cache(maxsize=64)
def _term_dates(year: int, tz_name: str) -> dict[str, date]:
    """全年节气日期（按年+时区缓存；返回值只读共享，调用方不得修改）。"""
    return {t.name: t.local.date() for t in terms_of_year(year, tz_name)}


def _resolve_person_year_zhi(person: PersonSpec | None, cal: CalendarConfig) -> str | None:
    """命主年支：优先人工覆盖，其次由出生时间推算（以年柱口径）。"""
    if person is None:
        return None
    if person.year_zhi:
        return person.year_zhi
    if person.year_gz and len(person.year_gz) == 2:
        return person.year_gz[1]
    if person.birth_dt is not None:
        birth = person.birth_dt
        if birth.tzinfo is None:
            birth = birth.replace(tzinfo=ZoneInfo(cal.timezone))
        pillars = compute_four_pillars(birth, cal)
        return pillars.year.zhi
    return None


def build_context(
    course: CourseSpec,
    site: SiteSpec,
    task: TaskSpec,
    *,
    person: PersonSpec | None = None,
    cal: CalendarConfig | None = None,
    include_term_day_itself: bool = False,
    calibers: CaliberRegistry | None = None,
) -> dict[str, Any]:
    """构建评估上下文 ``ctx``。

    返回结构（DSL 白名单命名空间）::

        course.{year,month,day,hour}.{gan,zhi,ganzhi}
        site.{azimuth,mountain,facing,fenjin,lat,lon,jian,shan_jia_zhi,mountain_center_deg,offset_deg}
        person.{name,year_zhi,year_gz,provided}
        task.{kind,node,nodes,strictness,granularity}
        time.{datetime,date,jie,month_zhi,year_zhi,lunar,timezone}
        facts.{...}
    """
    cal = cal or CalendarConfig()
    creg = calibers or load_caliber_sets()
    tz = ZoneInfo(cal.timezone)
    dt = course.dt if course.dt.tzinfo else course.dt.replace(tzinfo=tz)

    pillars = compute_four_pillars(dt, cal, lon=site.lon)

    mountain: Mountain = mountain_of_azimuth(site.azimuth_deg)
    facing: Mountain = facing_of(mountain)
    # 兼向阈值取自数值口径（QUESTION Q-021）：两说并存时改 config 即换口径，
    # 不改代码、不重跑测试。默认 zheng6_jian45（threshold=3.0），与历史行为一致。
    _jian_params = creg.params(CALIBER_JIANXIANG)
    _jian_threshold = float(_jian_params.get("threshold_deg", 3.0))
    jian = jian_xiang(mountain, threshold_deg=_jian_threshold)
    if jian in ZHI:
        shan_jia_zhi: str | None = jian
    elif mountain.name in ZHI:
        shan_jia_zhi = mountain.name
    else:
        shan_jia_zhi = None  # 四维山且不兼 → 无山家地支，相关规则降级 unknown

    fenjin = fenjin_of_azimuth(site.azimuth_deg)
    term_dates = _term_dates(dt.year, cal.timezone)
    # 日紫白的三元边界可能落在上一年（1 月的日课要回溯到上年冬至/霜降），
    # 故一并取上一年节气日期；terms_of_year 自带缓存，跨年不重复计算。
    term_dates_prev = _term_dates(dt.year - 1, cal.timezone)

    # ---- 两级事实缓存（C19 统一键）----
    # ① 日级键：**不含时柱**，只缓存与时辰无关的部分（节气/三煞/五黄/玄空/天星/董公…）；
    # ② 候选级：用 overlay_hour_facts 把 structure/旬空 hits/通关/三合局/斗首 按本时辰重算。
    # 为什么分两级：整包按候选缓存会把 derive_facts 从 365 次变成 4380 次（实测 2.7s→5.4s，
    # 超 3s 预算）；只按日缓存又会把首个子时的事实带给其余 11 个时辰（2026-11-02 的 P0）。
    # 两级拆分同时满足正确性与预算，且时变部分只有一个计算入口（registry 里的同名函数）。
    _day_key = stable_cache_key(
        "day_facts",
        pillars.year.name, pillars.month.name, pillars.day.name,
        mountain.name, facing.name if facing is not None else None,
        shan_jia_zhi, dt.astimezone(tz).date(), include_term_day_itself,
        creg.chosen(CALIBER_SANSHA), creg.chosen(CALIBER_NAYIN),
        creg.chosen(CALIBER_DOUSHO),
        creg.chosen(CALIBER_ZIBAI_FLY), creg.chosen(CALIBER_TIANDE_GUA),
        creg.chosen(CALIBER_JIANXIANG),
        creg.alternatives(CALIBER_NAYIN),
    )
    base_facts = _FACTS_CACHE.get(_day_key)
    if base_facts is None:
        base_facts = derive_facts(
            year_zhi=pillars.year.zhi,
            month_zhi=pillars.month.zhi,
            day_ganzhi=pillars.day.name,
            gans=list(pillars.gans),
            zhis=list(pillars.zhis),
            mountain=mountain,
            facing=facing,
            shan_jia_zhi=shan_jia_zhi,
            local_date=dt.astimezone(tz).date(),
            term_dates=term_dates,
            term_dates_prev=term_dates_prev,
            include_term_day_itself=include_term_day_itself,
            sansha_caliber=creg.chosen(CALIBER_SANSHA),
            nayin_caliber=creg.chosen(CALIBER_NAYIN),
            nayin_alternatives=creg.alternatives(CALIBER_NAYIN),
            doushou_tu_changsheng=creg.chosen(CALIBER_DOUSHO),
            zibai_fly=creg.chosen(CALIBER_ZIBAI_FLY),
            tiande_caliber=creg.chosen(CALIBER_TIANDE_GUA),
        )
        if len(_FACTS_CACHE) >= _FACTS_CACHE_MAX:
            _FACTS_CACHE.clear()
        _FACTS_CACHE[_day_key] = base_facts
    facts = overlay_hour_facts(
        base_facts,
        gans=list(pillars.gans),
        zhis=list(pillars.zhis),
        shan_jia_zhi=shan_jia_zhi,
        day_ganzhi=pillars.day.name,
        month_zhi=pillars.month.zhi,
        mountain_name=mountain.name,
        doushou_tu_changsheng=creg.chosen(CALIBER_DOUSHO),
        zibai_fly=creg.chosen(CALIBER_ZIBAI_FLY),
    )

    person_ctx: dict[str, Any] = {}
    person_year_zhi = _resolve_person_year_zhi(person, cal)
    if person is not None:
        person_ctx = {
            "name": person.name,
            "year_zhi": person_year_zhi,
            "year_gz": person.year_gz,
            "gender": person.gender,
            "provided": person.provided,
        }

    return {
        "course": {
            "year": pillars.year.to_dict(),
            "month": pillars.month.to_dict(),
            "day": pillars.day.to_dict(),
            "hour": pillars.hour.to_dict(),
            "bazi": pillars.bazi,
        },
        "site": {
            "azimuth": round(mountain.azimuth, 4),
            "mountain": mountain.name,
            "facing": facing.name,
            "mountain_center_deg": mountain.center_deg,
            "offset_deg": round(mountain.offset_deg, 4),
            "jian": jian,
            "shan_jia_zhi": shan_jia_zhi,
            # 兼向阈值口径回显：报告必须能回答"这次用的是 3.0° 还是 4.5°"（Q-021）
            "jian_caliber": creg.chosen(CALIBER_JIANXIANG),
            "jian_threshold_deg": _jian_threshold,
            "fenjin": {
                "slot": fenjin.slot,
                "center_deg": round(fenjin.center_deg, 4),
                "declared": site.fenjin,
            },
            "lat": site.lat,
            "lon": site.lon,
            "measure_method": site.measure_method,
            "angle_uncertainty_deg": site.angle_uncertainty_deg,
        },
        "person": person_ctx,
        "task": {
            "kind": task.kind,
            "node": course.node,
            "nodes": list(task.nodes),
            "strictness": task.strictness,
            "granularity": task.granularity,
        },
        "time": {
            "datetime": dt.isoformat(),
            "date": dt.astimezone(tz).date().isoformat(),
            "jie": pillars.jie_name,
            "month_zhi": pillars.month.zhi,
            "year_zhi": pillars.year.zhi,
            "day_zhi": pillars.day.zhi,
            "hour_zhi": pillars.hour.zhi,
            "lunar": pillars.lunar,
            "timezone": cal.timezone,
            "day_boundary": cal.day_boundary,
            "use_true_solar_time": cal.use_true_solar_time,
            "ym_time_ref": cal.ym_time_ref,
            "hour_time_ref": cal.hour_time_ref,
        },
        "facts": facts,
        "_meta": {
            "calendar_config": cal.to_manifest(),
            "calibers": creg.to_manifest(),
            "person_provided": person.provided if person else False,
            "shan_jia_derivation": "兼向取兼山" if jian in ZHI else "本山为地支",
        },
    }


# --------------------------------------------------------------------------- #
# 输出 JSON Schema（契约测试用；手写以避免引入 pydantic 依赖）
# --------------------------------------------------------------------------- #
EVALUATION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ZeriEvaluation",
    "type": "object",
    "required": [
        "candidate",
        "state",
        "tier",
        "publishable",
        "vectors",
        "per_school",
        "conflicts",
        "unknowns",
        "manifest",
    ],
    "additionalProperties": False,
    "properties": {
        "candidate": {"type": "string"},
        "state": {"type": "string", "enum": ["不可用", "可用", "存疑"]},
        "tier": {
            "type": "string",
            "enum": ["REJECTED", "NEEDS_REVIEW", "ACCEPTABLE", "PREFERRED"],
        },
        "publishable": {"type": "boolean"},
        "schema_version": {"type": "integer", "minimum": 2,
                           "description": "v2 = ADR-0014（source_status/doubt/declared_severity/controversial/demo_hits）"},
        "vectors": {
            "type": "object",
            "required": [
                "hard_fail_count",
                "strong_avoid_count",
                "conflict_count",
                "unknown_count",
                "positive_count",
            ],
            "properties": {
                "hard_fail_count": {"type": "integer", "minimum": 0},
                "strong_avoid_count": {"type": "integer", "minimum": 0},
                "conflict_count": {"type": "integer", "minimum": 0},
                "unknown_count": {"type": "integer", "minimum": 0},
                "positive_count": {"type": "integer", "minimum": 0},
                "note_count": {"type": "integer", "minimum": 0},
            },
        },
        "per_school": {"type": "object"},
        "structural": {"type": "array"},
        "required_rule_ids": {"type": "array"},
        "required_blockers": {"type": "array"},
        "required_satisfied_count": {"type": "integer", "minimum": 0},
        "conflicts": {"type": "array"},
        "unknowns": {"type": "array"},
        "manifest": {
            "type": "object",
            "required": ["input_hash", "rule_lib_version", "engine_version"],
            "properties": {
                "input_hash": {"type": "string"},
                "facts_hash": {"type": "string"},
                "rule_lib_version": {"type": "string"},
                "engine_version": {"type": "string"},
                "config": {"type": "object"},
            },
        },
    },
}


def validate_schema(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """极简 JSON Schema 校验器（支持 type/required/enum/properties/items/minimum）。

    只为契约测试服务；不追求完整实现。返回错误信息列表（空表示通过）。
    """
    errors: list[str] = []
    expected = schema.get("type")
    if expected:
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
        }
        py_type = type_map.get(expected)
        if py_type is not None:
            if expected == "integer" and isinstance(instance, bool):
                errors.append(f"{path}: 期望 integer，得到 boolean")
            elif not isinstance(instance, py_type):
                errors.append(f"{path}: 期望 {expected}，得到 {type(instance).__name__}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: 值 {instance!r} 不在枚举 {schema['enum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: 缺少必填字段 {key}")
        for key, sub in (schema.get("properties") or {}).items():
            if key in instance:
                errors.extend(validate_schema(instance[key], sub, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            extra = set(instance) - set((schema.get("properties") or {}))
            if extra:
                errors.append(f"{path}: 存在未声明字段 {sorted(extra)}")

    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errors.extend(validate_schema(item, schema["items"], f"{path}[{i}]"))

    if "minimum" in schema and isinstance(instance, (int, float)) and instance < schema["minimum"]:
        errors.append(f"{path}: {instance} < minimum {schema['minimum']}")

    return errors


MINIMAL_SCHEMA_VALIDATOR = validate_schema
