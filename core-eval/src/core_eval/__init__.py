"""core-eval：择日引擎判定层。

三态判定 + 分层向量 + 派别并列 + 分歧度 + 敏感性分析 + 排序。
**禁止**在本层计算天文量（一律经 core-time 接口，由 app 层注入）。
**禁止**输出单一总分。
"""

from __future__ import annotations

from .disagreement import (
    STATE_TO_NUM,
    aggregate_disagreement,
    disagreement_of,
    disagreement_of_evaluation,
    most_divisive,
)
from .engine import (
    ENGINE_VERSION,
    STATE_BLOCKED,
    STATE_OK,
    STATE_UNSURE,
    STRICTNESS_LOOSE,
    STRICTNESS_NORMAL,
    STRICTNESS_STRICT,
    TIER_ACCEPTABLE,
    TIER_NEEDS_REVIEW,
    TIER_PREFERRED,
    TIER_REJECTED,
    UNKNOWN_CALIBER,
    UNKNOWN_MISSING_INPUT,
    UNKNOWN_UNVERIFIED,
    EvalConfig,
    Evaluation,
    Judgment,
    SchoolResult,
    classify_unknown,
    evaluate,
    render_explanation,
)
from .ranker import TIER_RANK, explain_sort, pareto_front, rank, sort_key, top_k
from .sensitivity import (
    DEFAULT_PERTURBATIONS,
    Flip,
    Perturbation,
    SensitivityReport,
    analyze,
)
from .structure import ZIXING_SET, StructureHit, StructureReport, detect_structure

__all__ = [name for name in dir() if not name.startswith("_")]

__version__ = "0.1.0"
