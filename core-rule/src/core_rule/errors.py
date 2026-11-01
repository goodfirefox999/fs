"""规则层异常。异常类型本身就是契约的一部分，禁止上层用 ``except Exception`` 吞掉。"""

from __future__ import annotations

__all__ = [
    "RuleError",
    "DSLValidationError",
    "UnknownFactError",
    "LifecycleError",
    "SignatureError",
    "RuleReferenceError",
]


class RuleError(Exception):
    """规则层基类异常。"""


class DSLValidationError(RuleError):
    """DSL 结构非法（字段缺失、算子未知、深度超限、命名空间越界等）。"""

    def __init__(self, message: str, *, rule_id: str | None = None, path: str | None = None) -> None:
        self.rule_id = rule_id
        self.path = path
        prefix = f"[{rule_id}] " if rule_id else ""
        where = f" @{path}" if path else ""
        super().__init__(f"{prefix}{message}{where}")


class UnknownFactError(RuleError):
    """求值时 fact 路径不存在。**求值器不抛此异常**，只在显式严格模式下使用。"""


class LifecycleError(RuleError):
    """规则生命周期状态迁移非法。"""


class SignatureError(RuleError):
    """``status`` 变更缺少人类签名（``Verified-By:``）。"""


class RuleReferenceError(RuleError):
    """规则引用完整性失败（如 ``tests`` 指向的用例不存在）。"""
