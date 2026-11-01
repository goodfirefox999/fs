"""app-zeri：择日引擎应用层（CLI / 报告 / 用例运行器）。

本层只做**组合与编排**：历法计算经 ``core-time``，判定经 ``core-eval``，规则经 ``core-rule``。
不写任何计算逻辑（架构铁律 1）。
"""

from __future__ import annotations

from .case_runner import CaseOutcome, CaseRunReport, cohen_kappa, run_cases
from .generator import (
    HOUR_SAMPLE_HOURS,
    GenResult,
    NoSolution,
    candidate_datetimes,
    generate,
    iter_candidates,
)
from .report import (
    DISCLAIMER,
    render_generation_markdown,
    render_json,
    render_markdown,
    render_manifest_block,
)
from .schemas import (
    EVALUATION_SCHEMA,
    CourseSpec,
    PersonSpec,
    SiteSpec,
    TaskSpec,
    build_context,
    validate_schema,
)
from .verifier import VerifyResult, verify, verify_context

__all__ = [name for name in dir() if not name.startswith("_")]

__version__ = "0.1.0"
