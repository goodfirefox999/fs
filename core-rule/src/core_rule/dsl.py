"""规则 DSL：解析、校验、求值（唯一求值器，禁止旁路）。

三值逻辑
--------
求值结果为 ``True`` / ``False`` / ``None``（unknown）。``None`` 的语义是
"输入不足或事实不可得"，**不得**被吞掉或当作 False：

- ``all``：任一 False → False；否则任一 None → None；否则 True
- ``any``：任一 True → True；否则任一 None → None；否则 False
- ``not``：True→False，False→True，None→None

unknown 会使该规则判定降级为"存疑"，并在报告中标注"输入不足"（见 5.2 节）。

fact 白名单
-----------
根命名空间仅允许：``course.*``、``site.*``、``person.*``、``task.*``、``time.*``、``facts.*``。
越界在**加载期**即报错（不是运行期），以保证规则库不可能访问未声明数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .errors import DSLValidationError

__all__ = [
    "ALLOWED_ROOTS",
    "OPS",
    "MAX_DEPTH",
    "EvalOutcome",
    "validate_condition",
    "eval_condition",
    "resolve_path",
    "condition_depth",
    "collect_fact_paths",
]

#: fact 根命名空间白名单
ALLOWED_ROOTS: frozenset[str] = frozenset(
    {"course", "site", "person", "task", "time", "facts"}
)

#: 组合节点键
COMBINATORS = frozenset({"all", "any", "not"})

#: 条件树最大嵌套深度
MAX_DEPTH = 4


# --------------------------------------------------------------------------- #
# 路径解析
# --------------------------------------------------------------------------- #
_MISSING = object()


def resolve_path(ctx: dict[str, Any], path: str) -> tuple[bool, Any]:
    """按点路径取值，返回 ``(是否找到, 值)``。

    路径中的列表下标用数字段表示，例如 ``facts.sansha.year.mountains.0``。
    """
    if not isinstance(path, str) or not path:
        return False, None
    node: Any = ctx
    for part in path.split("."):
        if isinstance(node, dict):
            if part not in node:
                return False, None
            node = node[part]
        elif isinstance(node, (list, tuple)):
            if not part.isdigit():
                return False, None
            idx = int(part)
            if idx >= len(node):
                return False, None
            node = node[idx]
        else:
            return False, None
    return True, node


def _root_of(path: str) -> str:
    return path.split(".", 1)[0]


# --------------------------------------------------------------------------- #
# 算子
# --------------------------------------------------------------------------- #
def _as_set(value: Any) -> set[Any] | None:
    if isinstance(value, str):
        return set(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return set(value)
    if isinstance(value, dict):
        return set(value.keys())
    return None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _op_eq(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    return a == b


def _op_ne(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    return a != b


def _op_in(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    if b is None:
        raise DSLValidationError("in 算子需要 value 为集合/列表/字符串")
    if isinstance(b, dict):
        return a in b
    return a in b


def _op_nin(a: Any, b: Any, ctx: dict[str, Any]) -> bool:
    return not _op_in(a, b, ctx)


def _op_intersects(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    sa, sb = _as_set(a), _as_set(b)
    if sa is None or sb is None:
        raise DSLValidationError("intersects 算子两侧必须是集合/列表/字符串")
    return bool(sa & sb)


def _op_gte(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    if not _is_number(a) or not _is_number(b):
        raise DSLValidationError("gte 算子需要数值")
    return a >= b


def _op_lte(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    if not _is_number(a) or not _is_number(b):
        raise DSLValidationError("lte 算子需要数值")
    return a <= b


def _op_between(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    if not _is_number(a):
        raise DSLValidationError("between 算子需要左侧为数值")
    if not isinstance(b, (list, tuple)) or len(b) != 2:
        raise DSLValidationError("between 算子 value 必须是 [min, max]")
    lo, hi = b
    if not _is_number(lo) or not _is_number(hi):
        raise DSLValidationError("between 边界必须是数值")
    return lo <= a <= hi


def _op_exists(a: Any, _b: Any, _ctx: dict[str, Any]) -> bool:
    if a is None:
        return False
    if isinstance(a, (str, list, tuple, dict, set)) and len(a) == 0:
        return False
    return True


def _op_same_group(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    """``a`` 与 ``b`` 是否同属某干支组。

    ``value`` 形如 ``{path: course.day.zhi, kind: sanhe}``；``kind`` 支持
    ``sanhe`` / ``sanhui`` / ``liuhe`` / ``chong`` / ``hai`` / ``xing`` / ``po``。
    """
    if not isinstance(b, dict) or "path" not in b:
        raise DSLValidationError("same_group 的 value 必须形如 {path: ..., kind: ...}")
    found, other = resolve_path(_ctx, b["path"])
    if not found or other is None:
        raise _UnknownFact(b["path"])
    kind = b.get("kind", "sanhe")
    from core_symbol.ganzhi import same_group  # 延迟导入，避免循环依赖

    return same_group(str(a), str(other), kind)


def _op_count_gte(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    if a is None:
        raise DSLValidationError("count_gte 需要可计数对象")
    if not isinstance(b, (int, float)):
        raise DSLValidationError("count_gte 的 value 必须是数值")
    return len(a) >= b


def _op_count_eq(a: Any, b: Any, _ctx: dict[str, Any]) -> bool:
    if a is None:
        raise DSLValidationError("count_eq 需要可计数对象")
    return len(a) == b


OPS: dict[str, Callable[[Any, Any, dict[str, Any]], bool]] = {
    "eq": _op_eq,
    "ne": _op_ne,
    "in": _op_in,
    "nin": _op_nin,
    "intersects": _op_intersects,
    "gte": _op_gte,
    "lte": _op_lte,
    "between": _op_between,
    "exists": _op_exists,
    "same_group": _op_same_group,
    "count_gte": _op_count_gte,
    "count_eq": _op_count_eq,
}


class _UnknownFact(Exception):
    """内部信号：求值时 fact 缺失 → unknown。"""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(path)


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def condition_depth(cond: Any, _depth: int = 1) -> int:
    """条件树最大嵌套深度（根为 1）。"""
    if not isinstance(cond, dict):
        return _depth
    for key in COMBINATORS:
        if key in cond:
            body = cond[key]
            if key == "not":
                return condition_depth(body, _depth + 1)
            if not isinstance(body, list):
                return _depth + 1
            return max([_depth] + [condition_depth(item, _depth + 1) for item in body])
    return _depth


def collect_fact_paths(cond: Any, out: list[str] | None = None) -> list[str]:
    """收集条件树中引用的全部 fact 路径（含 ``value_from`` 与 ``same_group.path``）。"""
    out = [] if out is None else out
    if not isinstance(cond, dict):
        return out
    if "fact" in cond:
        if isinstance(cond["fact"], str):
            out.append(cond["fact"])
        vf = cond.get("value_from")
        if isinstance(vf, str):
            out.append(vf)
        value = cond.get("value")
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            out.append(value["path"])
        return out
    for key in COMBINATORS:
        if key in cond:
            body = cond[key]
            if key == "not":
                collect_fact_paths(body, out)
            elif isinstance(body, list):
                for item in body:
                    collect_fact_paths(item, out)
    return out


def validate_condition(cond: Any, *, rule_id: str | None = None, depth: int = 1) -> None:
    """加载期校验：结构、深度、算子、命名空间白名单。非法即抛 ``DSLValidationError``。"""
    if depth > MAX_DEPTH:
        raise DSLValidationError(
            f"条件树深度超过 {MAX_DEPTH}", rule_id=rule_id, path=f"depth={depth}"
        )
    if not isinstance(cond, dict):
        raise DSLValidationError(f"条件节点必须是对象，得到 {type(cond).__name__}", rule_id=rule_id)

    keys = set(cond)
    combinators = keys & COMBINATORS
    if combinators:
        if len(combinators) > 1:
            raise DSLValidationError(f"同一节点不得混用多个组合键: {sorted(combinators)}", rule_id=rule_id)
        key = combinators.pop()
        if key == "not":
            validate_condition(cond["not"], rule_id=rule_id, depth=depth + 1)
            return
        body = cond[key]
        if not isinstance(body, list) or not body:
            raise DSLValidationError(f"{key} 必须是非空数组", rule_id=rule_id)
        for item in body:
            validate_condition(item, rule_id=rule_id, depth=depth + 1)
        return

    if "fact" not in cond:
        raise DSLValidationError(f"原子节点缺少 fact 字段: {sorted(keys)}", rule_id=rule_id)
    fact = cond["fact"]
    if not isinstance(fact, str):
        raise DSLValidationError("fact 必须是字符串路径", rule_id=rule_id)
    root = _root_of(fact)
    if root not in ALLOWED_ROOTS:
        raise DSLValidationError(
            f"fact 根命名空间越界: {root}（允许 {sorted(ALLOWED_ROOTS)}）", rule_id=rule_id, path=fact
        )
    op = cond.get("op")
    if op not in OPS:
        raise DSLValidationError(f"未知算子: {op}（允许 {sorted(OPS)}）", rule_id=rule_id, path=fact)
    if op not in ("exists",) and "value" not in cond and "value_from" not in cond:
        raise DSLValidationError(f"算子 {op} 缺少 value/value_from", rule_id=rule_id, path=fact)
    vf = cond.get("value_from")
    if vf is not None:
        if not isinstance(vf, str) or _root_of(vf) not in ALLOWED_ROOTS:
            raise DSLValidationError(f"value_from 路径非法: {vf}", rule_id=rule_id, path=fact)
    value = cond.get("value")
    if op == "same_group":
        if not isinstance(value, dict) or "path" not in value:
            raise DSLValidationError(
                "same_group 的 value 必须形如 {path: ..., kind: ...}", rule_id=rule_id, path=fact
            )
        if _root_of(str(value["path"])) not in ALLOWED_ROOTS:
            raise DSLValidationError(
                f"same_group.path 命名空间越界: {value['path']}", rule_id=rule_id, path=fact
            )
        from core_symbol.ganzhi import same_group  # noqa: F401 仅校验 kind 可用性

    extra = keys - {"fact", "op", "value", "value_from", "note"}
    if extra:
        raise DSLValidationError(f"原子节点含未知字段: {sorted(extra)}", rule_id=rule_id, path=fact)


# --------------------------------------------------------------------------- #
# 求值
# --------------------------------------------------------------------------- #
@dataclass
class EvalOutcome:
    """求值结果：``value`` 为三值；``unknown_paths`` 记录导致 unknown 的路径。"""

    value: bool | None
    unknown_paths: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # pragma: no cover - 防止误用真值
        raise TypeError("EvalOutcome 请显式使用 .value（三值语义）")


def _eval_atom(cond: dict[str, Any], ctx: dict[str, Any]) -> EvalOutcome:
    path = cond["fact"]
    found, value = resolve_path(ctx, path)
    if not found or value is None:
        return EvalOutcome(None, [path])

    op = cond["op"]
    if "value_from" in cond:
        target_path = cond["value_from"]
        found_t, target = resolve_path(ctx, target_path)
        if not found_t or target is None:
            return EvalOutcome(None, [target_path])
        expected = target
    else:
        expected = cond.get("value")

    if op == "exists":
        return EvalOutcome(bool(OPS["exists"](value, None, ctx)), [])

    try:
        return EvalOutcome(bool(OPS[op](value, expected, ctx)), [])
    except _UnknownFact as exc:
        return EvalOutcome(None, [exc.path])


def eval_condition(cond: dict[str, Any], ctx: dict[str, Any]) -> EvalOutcome:
    """对条件树求值，返回三值结果与 unknown 原因路径。"""
    keys = set(cond)
    if "all" in keys:
        unknown: list[str] = []
        for item in cond["all"]:
            res = eval_condition(item, ctx)
            if res.value is False:
                return EvalOutcome(False, [])
            if res.value is None:
                unknown.extend(res.unknown_paths)
        return EvalOutcome(None, sorted(set(unknown))) if unknown else EvalOutcome(True, [])

    if "any" in keys:
        unknown = []
        for item in cond["any"]:
            res = eval_condition(item, ctx)
            if res.value is True:
                return EvalOutcome(True, [])
            if res.value is None:
                unknown.extend(res.unknown_paths)
        return EvalOutcome(None, sorted(set(unknown))) if unknown else EvalOutcome(False, [])

    if "not" in keys:
        res = eval_condition(cond["not"], ctx)
        if res.value is None:
            return res
        return EvalOutcome(not res.value, [])

    return _eval_atom(cond, ctx)


def iter_atoms(cond: Any) -> Iterable[dict[str, Any]]:
    """遍历条件树中的原子节点。"""
    if not isinstance(cond, dict):
        return
    if "fact" in cond:
        yield cond
        return
    for key in COMBINATORS:
        if key in cond:
            body = cond[key]
            if key == "not":
                yield from iter_atoms(body)
            elif isinstance(body, list):
                for item in body:
                    yield from iter_atoms(item)
