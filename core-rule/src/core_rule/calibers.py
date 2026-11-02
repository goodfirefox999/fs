"""口径注册表（规则层，配置即数据）。

背景
----
择日里几乎所有"有争议"的东西，本质是**口径**（caliber）不同：
三煞是判到方位组还是判到劫/灾/岁？坐山纳音按穿山七十二龙还是一百二十分金？
月五黄按年上起月还是月上起月？

如果把口径写死在代码里，同一条规则在不同口径下会给出不同结论，而报告看不出来。
本模块把口径变成**命名注册表**：

1. 每个口径有唯一名字、状态（``已考证``/``待考证``/``有争议``）与说明；
2. 一次评估必须显式指定用哪个口径（或使用默认值），报告强制回显；
3. 未裁定口径下，相关规则一律 ``unknown``，但报告给出**对比式提示**
   （每个口径各自缺什么、选了会怎样），而不是一句"未知"了事。

与规则状态的关系
----------------
口径状态与规则状态**独立**：一条 ``已考证`` 的规则，如果依赖的口径未裁定，
其结论仍然不可用。反之，口径已裁定也不能把 ``待考证`` 规则变成已考证。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import DSLValidationError

__all__ = [
    "CaliberSpec",
    "CaliberSet",
    "CaliberRegistry",
    "load_caliber_sets",
    "DEFAULT_CALIBERS_DIR",
    "CALIBER_SANSHA",
    "CALIBER_NAYIN",
    "CALIBER_DOUSHO",
    "CALIBER_ZIBAI_FLY",
    "CALIBER_TIANDE_GUA",
    "CALIBER_JIANXIANG",
]

CALIBER_SANSHA = "sansha"
CALIBER_NAYIN = "nayin"
#: 斗首得位——土行长生位（土寄坤 / 土寄艮）
CALIBER_DOUSHO = "doushou_tu_changsheng"
#: 紫白日/时盘九宫飞布方向（顺飞 / 逆飞）
CALIBER_ZIBAI_FLY = "zibai_fly"
#: 天德四维卦位取支（整宫并集 / 渊海单支 / 考原单支）
CALIBER_TIANDE_GUA = "tiande_guaxiang"
#: 兼向阈值（正针带半宽）：3.0°（正针 6°）或 4.5°（正针 9°）——数值口径，QUESTION Q-021
CALIBER_JIANXIANG = "jianxiang"

DEFAULT_CALIBERS_DIR = Path(__file__).resolve().parents[2] / "config" / "calibers"

_CALIBER_STATUSES = ("已考证", "待考证", "有争议")


@dataclass(frozen=True)
class CaliberSpec:
    """一个命名口径。

    ``params`` 承载**数值型**口径（如兼向阈值 3.0°/4.5°）。有了它，
    "同一个口径、只是常数不同"的分歧不必再写成两个分支，改 config 即换口径——
    师傅裁定后不用改代码、不用重跑测试（QUESTION Q-021）。
    """

    name: str
    status: str
    description: str
    note: str = ""
    requires: tuple[str, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "description": self.description,
            "note": self.note,
            "requires": list(self.requires),
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class CaliberSet:
    """一组同类口径（如"三煞口径"）。"""

    set_name: str
    description: str
    default: str
    calibers: dict[str, CaliberSpec] = field(default_factory=dict)

    def get(self, name: str | None) -> CaliberSpec:
        key = name or self.default
        if key not in self.calibers:
            raise DSLValidationError(
                f"未声明的口径: {key}（{self.set_name} 允许 {sorted(self.calibers)}）"
            )
        return self.calibers[key]

    def is_decided(self, name: str | None) -> bool:
        return self.get(name).status == "已考证"

    def alternatives(self) -> list[dict[str, Any]]:
        """对比式提示：列出全部口径及各自状态/所需输入。"""
        return [spec.to_dict() for spec in self.calibers.values()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "set": self.set_name,
            "description": self.description,
            "default": self.default,
            "calibers": {k: v.to_dict() for k, v in self.calibers.items()},
        }


@dataclass(frozen=True)
class CaliberRegistry:
    """全部口径集合。"""

    sets: dict[str, CaliberSet] = field(default_factory=dict)
    selection: dict[str, str] = field(default_factory=dict)

    def get_set(self, set_name: str) -> CaliberSet:
        if set_name not in self.sets:
            raise DSLValidationError(f"未声明的口径组: {set_name}")
        return self.sets[set_name]

    def chosen(self, set_name: str) -> str:
        """当前选用的口径名（未显式选择时用默认值）。"""
        cs = self.get_set(set_name)
        return self.selection.get(set_name) or cs.default

    def is_decided(self, set_name: str) -> bool:
        cs = self.get_set(set_name)
        return cs.is_decided(self.chosen(set_name))

    def alternatives(self, set_name: str) -> list[dict[str, Any]]:
        return self.get_set(set_name).alternatives()

    def params(self, set_name: str) -> dict[str, Any]:
        """当前选用口径的数值参数（未显式选择时用默认值的）。"""
        return dict(self.get_set(set_name).get(self.chosen(set_name)).params)

    def with_selection(self, selection: dict[str, str]) -> "CaliberRegistry":
        merged = {**self.selection, **selection}
        for set_name, caliber in merged.items():
            if set_name in self.sets:
                self.get_set(set_name).get(caliber)  # 校验存在
        return CaliberRegistry(sets=dict(self.sets), selection=merged)

    def to_manifest(self) -> dict[str, Any]:
        return {
            "selection": {k: self.chosen(k) for k in self.sets},
            "sets": {k: v.to_dict() for k, v in self.sets.items()},
        }


def load_caliber_sets(directory: Path | str | None = None) -> CaliberRegistry:
    """从目录加载全部 ``*.yaml`` 口径定义。"""
    root = Path(directory) if directory else DEFAULT_CALIBERS_DIR
    if not root.exists():
        return CaliberRegistry()
    sets: dict[str, CaliberSet] = {}
    for path in sorted(root.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise DSLValidationError(f"{path}: 顶层必须是映射")
        set_name = data.get("caliber_set")
        if not set_name:
            raise DSLValidationError(f"{path}: 缺少 caliber_set")
        calibers_raw = data.get("calibers") or {}
        if not calibers_raw:
            raise DSLValidationError(f"{path}: calibers 不得为空")
        calibers: dict[str, CaliberSpec] = {}
        for name, spec in calibers_raw.items():
            spec = spec or {}
            status = spec.get("status", "待考证")
            if status not in _CALIBER_STATUSES:
                raise DSLValidationError(f"{path}: 口径 {name} 的 status 非法: {status}")
            calibers[name] = CaliberSpec(
                name=name,
                status=status,
                description=str(spec.get("description", "")),
                note=str(spec.get("note", "")),
                requires=tuple(spec.get("requires") or ()),
                params=dict(spec.get("params") or {}),
            )
        default = data.get("default") or next(iter(calibers))
        if default not in calibers:
            raise DSLValidationError(f"{path}: default 口径 {default} 未定义")
        sets[set_name] = CaliberSet(
            set_name=set_name,
            description=str(data.get("description", "")),
            default=default,
            calibers=calibers,
        )
    return CaliberRegistry(sets=sets)
