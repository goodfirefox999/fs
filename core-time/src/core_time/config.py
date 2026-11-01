"""历法配置：所有存在争议的历法口径都必须是可配置项（附录 B）。

本模块只描述"用哪套口径"，不判断"哪套对"。任何默认值都会在报告 manifest 中回显。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

__all__ = ["CalendarConfig", "DayBoundary", "YearBoundary", "MonthBoundary"]

DayBoundary = Literal["early", "late"]
YearBoundary = Literal["lichun", "newyear"]
MonthBoundary = Literal["jieqi", "lunar"]


@dataclass(frozen=True)
class CalendarConfig:
    """历法口径配置。

    参数
    ----
    timezone:
        IANA 时区名。默认 ``Asia/Shanghai``。历史时区变更不做（已知限制）。
    day_boundary:
        ``early`` = 子初换日（23:00 起算次日，即"早子时"归次日）；
        ``late`` = 子正换日（00:00 起算次日，23:00-24:00 仍属当日）。
    year_boundary:
        ``lichun`` = 立春换年；``newyear`` = 正月初一换年。
    month_boundary:
        ``jieqi`` = 节气换月（十二节）；``lunar`` = 农历月换月。
    use_true_solar_time:
        时辰是否用真太阳时。默认 False，报告中必须回显。
    longitude_for_solar_time:
        真太阳时所用经度；``None`` 时取 Site.lon。
    delta_t_model:
        ΔT 模型标识，写入 manifest。
    """

    timezone: str = "Asia/Shanghai"
    day_boundary: DayBoundary = "late"
    year_boundary: YearBoundary = "lichun"
    month_boundary: MonthBoundary = "jieqi"
    use_true_solar_time: bool = False
    #: 年/月柱的时间基准（决定"交节时刻与哪个时间比较"）。
    #: ``auto`` 跟随 ``use_true_solar_time``；``civil`` 强制民用时；``true_solar`` 强制真太阳时。
    #: 传统实践常见"年月柱用钟表时比交节、时柱用真太阳时"的混合口径，
    #: 故两者独立配置（ADR-0011）。
    ym_time_ref: str = "auto"
    #: 日/时柱的时间基准（同时决定换日边界用哪个时间）。
    hour_time_ref: str = "auto"
    longitude_for_solar_time: float | None = None
    delta_t_model: str = "espenak-meeus-anchor-linear-v1"
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.day_boundary not in ("early", "late"):
            raise ValueError(f"day_boundary 非法: {self.day_boundary}")
        if self.year_boundary not in ("lichun", "newyear"):
            raise ValueError(f"year_boundary 非法: {self.year_boundary}")
        if self.month_boundary not in ("jieqi", "lunar"):
            raise ValueError(f"month_boundary 非法: {self.month_boundary}")
        for name, value in (("ym_time_ref", self.ym_time_ref), ("hour_time_ref", self.hour_time_ref)):
            if value not in ("auto", "civil", "true_solar"):
                raise ValueError(f"{name} 非法: {value}（允许 auto/civil/true_solar）")

    def use_true_solar_for(self, ref: str) -> bool:
        """``auto`` 跟随全局开关；其余显式指定。"""
        return ref == "true_solar" or (ref == "auto" and self.use_true_solar_time)

    def to_manifest(self) -> dict[str, Any]:
        """报告回显用的参数快照（去掉不可序列化项）。"""
        data = asdict(self)
        data.pop("extra", None)
        return data

    def with_overrides(self, **kwargs: Any) -> "CalendarConfig":
        data = asdict(self)
        data.update({k: v for k, v in kwargs.items() if k in data})
        return CalendarConfig(**data)
