"""统一缓存键（C19，ADR-0014 遗留收拢）。

**所有**复合缓存点的键必须经 ``stable_cache_key`` 构造，禁止手写组合键。
背景（ADR-0014 第 216-218 行）：``_select_cached`` 曾只用 version 作键，同 id
同 version 改内容必然串味；日级事实缓存（schemas._FACTS_CACHE）是第五种手写
key——C19 是它的硬前置。键内带 schema 版本号（``KEY_SCHEMA``），键结构一变
整体失效，防跨语义投毒。

键形态：``v1:<sha256(canonical_json(parts))>``。parts 须为 JSON 可稳序列化值
（str/int/float/bool/None/tuple/list/dict；tuple 归一为 list）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = ["KEY_SCHEMA", "stable_cache_key"]

#: 键结构版本——构造方式变化（如新增字段语义）时 bump，全体缓存同时失效
KEY_SCHEMA = "v1"


def _canonical(obj: Any) -> Any:
    """递归归一：tuple→list；date/datetime→ISO 字符串（不可变值类型，等价替换）；
    其余原样；dict 键有序由 sort_keys 承担。"""
    import datetime as _dt

    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, (tuple, list)):
        return [_canonical(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _canonical(v) for k, v in obj.items()}
    raise TypeError(f"stable_cache_key 的 parts 含不可稳序列化类型: {type(obj).__name__}")


def stable_cache_key(*parts: Any) -> str:
    """统一缓存键：``v1:<sha256>``。同一 parts 恒同一键（进程内跨调用稳定）。"""
    payload = json.dumps(
        {"schema": KEY_SCHEMA, "parts": _canonical(list(parts))},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return f"{KEY_SCHEMA}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
