"""四柱（年月日时干支）计算（事实层）。

本模块只输出干支与派生历法量，不输出任何吉凶判断（铁律 3）。

约定（全部可配置，见 ``config.CalendarConfig``）
------------------------------------------------
- 年柱：立春 或 正月初一换年
- 月柱：以十二"节"为界，五虎遁起月干
- 日柱：子初（23:00）或 子正（00:00）换日
- 时柱：五鼠遁起时干；可选用真太阳时定时辰
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .config import CalendarConfig
from .ephemeris import julian_day_from_datetime
from .jieqi import jie_before, month_branch_index, terms_of_year
from .lunar import lunar_date_of
from .solar_time import true_solar_time

__all__ = [
    "GAN",
    "ZHI",
    "GANZHI60",
    "Pillar",
    "FourPillars",
    "ganzhi_index",
    "ganzhi_name",
    "jdn_of_date",
    "day_pillar_index",
    "compute_four_pillars",
]

GAN = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")
ZHI = ("子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥")
GANZHI60 = tuple(GAN[i % 10] + ZHI[i % 12] for i in range(60))

#: 五虎遁：年干 → 寅月月干（甲己丙作首…）
_YIN_MONTH_GAN = {0: 2, 1: 4, 2: 6, 3: 8, 4: 0, 5: 2, 6: 4, 7: 6, 8: 8, 9: 0}

#: 月支序号（子=0）→ 月序（寅=1 … 丑=12）
_BRANCH_TO_MONTH_ORDER = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 9, 11: 10, 0: 11, 1: 12}


def ganzhi_index(gan: str, zhi: str) -> int:
    """干支名 → 六十甲子序号（甲子=0）。非法组合抛 ``ValueError``。"""
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    idx = (gi * 6 - zi * 5) % 60
    if GANZHI60[idx] != gan + zhi:
        raise ValueError(f"非法干支组合: {gan}{zhi}")
    return idx


def ganzhi_name(index: int) -> str:
    return GANZHI60[index % 60]


def jdn_of_date(d: date) -> int:
    """公历日期的整数儒略日数（JDN，正午对齐）。"""
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def day_pillar_index(d: date) -> int:
    """公历日期 → 日柱六十甲子序号。基准：2000-01-01 为戊午（序号 54）。"""
    return (jdn_of_date(d) + 49) % 60


@dataclass(frozen=True)
class Pillar:
    """一柱。``index`` 为六十甲子序号（甲子=0）。"""

    gan: str
    zhi: str
    index: int

    @property
    def name(self) -> str:
        return self.gan + self.zhi

    @property
    def gan_index(self) -> int:
        return GAN.index(self.gan)

    @property
    def zhi_index(self) -> int:
        return ZHI.index(self.zhi)

    def to_dict(self) -> dict[str, Any]:
        return {"ganzhi": self.name, "gan": self.gan, "zhi": self.zhi, "index": self.index}

    @classmethod
    def from_index(cls, index: int) -> "Pillar":
        idx = index % 60
        return cls(gan=GAN[idx % 10], zhi=ZHI[idx % 12], index=idx)


@dataclass(frozen=True)
class FourPillars:
    """四柱及全部口径回显。"""

    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar
    #: 用于年柱归属的"命理年"
    pillar_year: int
    #: 月建节气名
    jie_name: str
    #: 计算日/时柱所用的时间（hour_time_ref 为真太阳时则为真太阳时读数）
    hour_reference: datetime
    #: 日界口径
    day_boundary: str
    #: 农历日期（本地）
    lunar: str
    #: 年月柱时间基准（auto/civil/true_solar）
    ym_time_ref: str = "auto"
    #: 日时柱时间基准（auto/civil/true_solar）
    hour_time_ref: str = "auto"
    #: 人工覆盖项（键 → 值），用于 provenance
    overrides: dict[str, Any] = field(default_factory=dict)

    @property
    def pillars(self) -> tuple[Pillar, Pillar, Pillar, Pillar]:
        return (self.year, self.month, self.day, self.hour)

    @property
    def zhis(self) -> tuple[str, str, str, str]:
        return (self.year.zhi, self.month.zhi, self.day.zhi, self.hour.zhi)

    @property
    def gans(self) -> tuple[str, str, str, str]:
        return (self.year.gan, self.month.gan, self.day.gan, self.hour.gan)

    @property
    def bazi(self) -> str:
        return " ".join(p.name for p in self.pillars)

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year.to_dict(),
            "month": self.month.to_dict(),
            "day": self.day.to_dict(),
            "hour": self.hour.to_dict(),
            "bazi": self.bazi,
            "pillar_year": self.pillar_year,
            "jie": self.jie_name,
            "hour_reference": self.hour_reference.isoformat(),
            "ym_time_ref": self.ym_time_ref,
            "hour_time_ref": self.hour_time_ref,
            "day_boundary": self.day_boundary,
            "lunar": self.lunar,
            "overrides": dict(self.overrides),
        }


def _pillar_year(dt: datetime, cfg: CalendarConfig) -> tuple[int, str]:
    """返回 (命理年, 依据说明)。"""
    tz = ZoneInfo(cfg.timezone)
    if cfg.year_boundary == "lichun":
        lichun = next(t for t in terms_of_year(dt.year, cfg.timezone) if t.name == "立春")
        return (dt.year if dt >= lichun.local else dt.year - 1), f"立春换年（{lichun.local:%Y-%m-%d %H:%M}）"
    lunar = lunar_date_of(dt.astimezone(tz).date(), cfg.timezone)
    return lunar.year, f"正月初一换年（农历{lunar.year}年）"


def compute_four_pillars(
    dt: datetime,
    cfg: CalendarConfig | None = None,
    lon: float | None = None,
) -> FourPillars:
    """计算 ``dt`` 的四柱。

    参数
    ----
    dt: 带时区的民用时。
    cfg: 历法口径配置，``None`` 时用默认值。
    lon: 站点经度（东经正）。仅在 ``cfg.use_true_solar_time`` 为真时使用。
    """
    cfg = cfg or CalendarConfig()
    if dt.tzinfo is None:
        raise ValueError("compute_four_pillars 需要带时区的时间")
    tz = ZoneInfo(cfg.timezone)
    local = dt.astimezone(tz)

    # 两个时间基准：年月柱用 ym_ref，日时柱用 hour_ref（ADR-0011）
    ym_true_solar = cfg.use_true_solar_for(cfg.ym_time_ref)
    hour_true_solar = cfg.use_true_solar_for(cfg.hour_time_ref)
    if ym_true_solar or hour_true_solar:
        use_lon = lon if lon is not None else cfg.longitude_for_solar_time
        if use_lon is None:
            raise ValueError("启用真太阳时但未提供经度")
    else:
        use_lon = None
    ym_ref = true_solar_time(local, use_lon) if ym_true_solar else local
    hour_ref = true_solar_time(local, use_lon) if hour_true_solar else local

    # ---- 年柱 ----
    # 年月柱用 ym_ref（默认跟随全局开关）；日时柱用 hour_ref。
    # 两者可独立配置：传统实践存在"年月柱用钟表时、时柱用真太阳时"的混合口径。
    pillar_year, year_basis = _pillar_year(ym_ref, cfg)
    year_idx = (pillar_year - 1984) % 60
    year_pillar = Pillar.from_index(year_idx)

    # ---- 月柱 ----
    jie = jie_before(ym_ref, cfg.timezone)
    branch = month_branch_index(ym_ref, cfg.timezone)
    order = _BRANCH_TO_MONTH_ORDER[branch]
    month_gan = (_YIN_MONTH_GAN[year_pillar.gan_index] + order - 1) % 10
    month_pillar = Pillar(gan=GAN[month_gan], zhi=ZHI[branch], index=ganzhi_index(GAN[month_gan], ZHI[branch]))

    # ---- 日柱 ----
    day_date = hour_ref.date()
    if cfg.day_boundary == "early" and hour_ref.hour >= 23:
        day_date = day_date + timedelta(days=1)
    day_pillar = Pillar.from_index(day_pillar_index(day_date))

    # ---- 时柱 ----
    hour_branch = ((hour_ref.hour + 1) // 2) % 12
    hour_gan = ((day_pillar.gan_index % 5) * 2 + hour_branch) % 10
    hour_pillar = Pillar(
        gan=GAN[hour_gan], zhi=ZHI[hour_branch], index=ganzhi_index(GAN[hour_gan], ZHI[hour_branch])
    )

    lunar = lunar_date_of(local.date(), cfg.timezone)
    overrides: dict[str, Any] = {"year_basis": year_basis}
    return FourPillars(
        year=year_pillar,
        month=month_pillar,
        day=day_pillar,
        hour=hour_pillar,
        pillar_year=pillar_year,
        jie_name=jie.name,
        hour_reference=hour_ref,
        ym_time_ref=cfg.ym_time_ref,
        hour_time_ref=cfg.hour_time_ref,
        day_boundary=cfg.day_boundary,
        lunar=str(lunar),
        overrides=overrides,
    )


def jd_of(dt: datetime) -> float:  # 便利再导出，避免上层直接依赖 ephemeris
    return julian_day_from_datetime(dt)
