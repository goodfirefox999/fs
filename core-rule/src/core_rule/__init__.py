"""core-rule：择日引擎规则层。

规则即数据：新增规则 = 新增 YAML + 测试，不改引擎代码（除非新增算子）。
本层负责 DSL 解析、求值、生命周期、provenance 与派别路由。
"""

from __future__ import annotations

from .calibers import (
    CALIBER_NAYIN,
    CALIBER_SANSHA,
    DEFAULT_CALIBERS_DIR,
    CaliberRegistry,
    CaliberSet,
    CaliberSpec,
    load_caliber_sets,
)
from .dsl import (
    ALLOWED_ROOTS,
    MAX_DEPTH,
    OPS,
    EvalOutcome,
    collect_fact_paths,
    condition_depth,
    eval_condition,
    resolve_path,
    validate_condition,
)
from .errors import (
    DSLValidationError,
    LifecycleError,
    RuleError,
    RuleReferenceError,
    SignatureError,
    UnknownFactError,
)
from .lifecycle import (
    AGENT_ALLOWED_STATUSES,
    ALLOWED_TRANSITIONS,
    HUMAN_ONLY_TARGETS,
    assert_signature,
    assert_transition,
    can_transition,
    requires_signature,
    validate_version_bump,
)
from .loader import RULE_ID_PATTERN, RuleSet, all_fact_paths, load_rule, load_ruleset
from .models import (
    RULE_STATUSES,
    SEVERITIES,
    SEVERITY_ORDER,
    TARGETS,
    AppliesTo,
    Rule,
    RuleStatus,
    Severity,
    Strictness,
    Target,
)
from .policy import (
    ConsensusPolicy,
    ConsensusSpec,
    SchoolPolicy,
    SchoolSpec,
    TaskKindSpec,
    load_consensus_config,
    load_school_policy,
    load_task_kinds,
)
from .provenance import Citation, Provenance, stable_hash
from .registry import CONFIG_DIR, RULES_DIR, RuleRegistry, default_registry

__all__ = [name for name in dir() if not name.startswith("_")]

__version__ = "0.1.0"
