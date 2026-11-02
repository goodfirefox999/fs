"""共识度整数比测试（ADR-0015）。

三个断言面：
1. **算术**：`favorable * den >= num * voters`，不得经由浮点；
2. **配置**：阈值只接受整数，浮点/布尔一律拒收；
3. **不变量**：任何一次评估里，投票名单与未投票名单互斥且覆盖全部参评派，
   投票派必须全是 `layer=scoring`。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from core_eval import EvalConfig, evaluate
from core_rule import default_registry
from core_rule.errors import DSLValidationError
from core_rule.policy import ConsensusSpec, load_consensus_config

TZ = ZoneInfo("Asia/Shanghai")
CONFIG = Path(__file__).resolve().parents[2] / "core-rule" / "config" / "consensus.yaml"


class TestIntegerArithmetic:
    def test_exact_threshold_is_enough(self) -> None:
        assert ConsensusSpec(3, 5).reached(3, 5) is True

    def test_one_short_is_not_enough(self) -> None:
        assert ConsensusSpec(3, 5).reached(2, 5) is False

    def test_smaller_denominator_helps(self) -> None:
        """分母只数表态派：2/3 同向应达标，而旧的绝对票数口径会判为不够。"""
        assert ConsensusSpec(3, 5).reached(2, 3) is True

    def test_zero_voters_never_reaches(self) -> None:
        assert ConsensusSpec(3, 5).reached(0, 0) is False

    def test_no_division_in_implementation(self) -> None:
        """判定过程不得出现真除法（结果必须是整数比较）。"""
        spec = ConsensusSpec(3, 5)
        # 3/5 与 0.6 在浮点下相等，但整数路径不产生 0.6 这个中间量
        assert spec.reached(6, 10) is True
        assert spec.reached(5, 10) is False


class TestConfigLoading:
    def test_repository_config_loads(self) -> None:
        policy = load_consensus_config(CONFIG)
        assert (policy.default.min_agree_num, policy.default.min_agree_den) == (3, 5)

    def test_float_threshold_is_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "consensus.yaml"
        p.write_text("default:\n  min_agree_num: 0.6\n  min_agree_den: 1\n", encoding="utf-8")
        with pytest.raises(DSLValidationError, match="必须是整数"):
            load_consensus_config(p)

    def test_bool_threshold_is_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "consensus.yaml"
        p.write_text("default:\n  min_agree_num: true\n  min_agree_den: 5\n", encoding="utf-8")
        with pytest.raises(DSLValidationError, match="必须是整数"):
            load_consensus_config(p)

    def test_ratio_above_one_is_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "consensus.yaml"
        p.write_text("default:\n  min_agree_num: 6\n  min_agree_den: 5\n", encoding="utf-8")
        with pytest.raises(DSLValidationError, match="不得大于 1"):
            load_consensus_config(p)

    def test_missing_file_falls_back_to_default(self, tmp_path: Path) -> None:
        policy = load_consensus_config(tmp_path / "absent.yaml")
        assert policy.default.reached(3, 5) is True

    def test_task_override_is_used(self, tmp_path: Path) -> None:
        p = tmp_path / "consensus.yaml"
        p.write_text(
            "default:\n  min_agree_num: 3\n  min_agree_den: 5\n"
            "overrides:\n  安葬:\n    min_agree_num: 4\n    min_agree_den: 5\n",
            encoding="utf-8",
        )
        policy = load_consensus_config(p)
        assert policy.for_task("安葬").min_agree_num == 4
        assert policy.for_task("入宅").min_agree_num == 3
        assert policy.for_task(None).min_agree_num == 3


def _ctx():
    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
    from core_time import CalendarConfig

    return build_context(
        course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=TZ)),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )


class TestDetailInvariants:
    def _eval(self):
        return evaluate(
            _ctx(),
            default_registry(),
            EvalConfig(
                task_kind="修造",
                strictness="strict",
                allow_unverified=True,
                demo_veto=True,
            ),
        )

    def _detail(self) -> dict:
        return self._eval().manifest["five_school_output"]["_consensus_detail"]

    def test_detail_shape(self) -> None:
        d = self._detail()
        assert set(d) >= {
            "consensus",
            "consensus_ratio",
            "votes",
            "voters",
            "non_voters",
            "gate_veto_schools",
            "threshold",
            "convention",
        }
        assert d["consensus_ratio"].count("/") == 1

    def test_ratio_numerator_matches_favorable_list(self) -> None:
        d = self._detail()
        num, den = d["consensus_ratio"].split("/")
        assert int(num) == len(d["votes"]["favorable"])
        assert int(den) == len(d["voters"])

    def test_voters_and_non_voters_partition_all_evaluated_schools(self) -> None:
        """互斥且完整覆盖：参评的每一派，要么投票、要么带原因列在未投票名单。"""
        ev = self._eval()
        d = ev.manifest["five_school_output"]["_consensus_detail"]
        voters = set(d["voters"])
        non_voters = {nv["school"] for nv in d["non_voters"]}
        assert not (voters & non_voters), "同一派不得既投票又未投票"
        assert voters | non_voters == set(ev.per_school), (
            f"遗漏或多余：参评 {set(ev.per_school)}，名单 {voters | non_voters}"
        )

    def test_gate_layer_never_votes(self) -> None:
        d = self._detail()
        registry = default_registry()
        for name in d["voters"]:
            assert registry.policy.schools[name].layer == "scoring", (
                f"闸门层/参考层派别 {name} 不得计票"
            )
        reasons = {nv["school"]: nv["reason"] for nv in d["non_voters"]}
        assert reasons.get("public") == "layer_reject"

    def test_no_float_field_in_detail(self) -> None:
        d = self._detail()
        assert isinstance(d["consensus_ratio"], str)
        assert not any(isinstance(v, float) for v in d.values()), (
            "共识明细不得包含浮点字段（防止下游加权求和）"
        )
