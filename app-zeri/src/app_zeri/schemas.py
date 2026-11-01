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

from core_rule.calibers import CALIBER_NAYIN, CALIBER_SANSHA, CaliberRegistry, load_caliber_sets
from core_symbol.ganzhi import ZHI
from core_symbol.mountain import Mountain, facing_of, fenjin_of_azimuth, jian_xiang, mountain_of_azimuth
from core_symbol.registry import derive_facts
from core_time import CalendarConfig, compute_four_pillars, terms_of_year

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


@lru_cache(maxsize=512)
def _term_dates(year: int, tz_name: str) -> dict[str, date]:
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
    jian = jian_xiang(mountain)
    if jian in ZHI:
        shan_jia_zhi: str | None = jian
    elif mountain.name in ZHI:
        shan_jia_zhi = mountain.name
    else:
        shan_jia_zhi = None  # 四维山且不兼 → 无山家地支，相关规则降级 unknown

    fenjin = fenjin_of_azimuth(site.azimuth_deg)
    term_dates = _term_dates(dt.year, cal.timezone)

    facts = derive_facts(
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
        include_term_day_itself=include_term_day_itself,
        sansha_caliber=creg.chosen(CALIBER_SANSHA),
        nayin_caliber=creg.chosen(CALIBER_NAYIN),
        nayin_alternatives=creg.alternatives(CALIBER_NAYIN),
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
