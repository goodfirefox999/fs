"""第五提交加固的反证测试：桶白名单断言 + demo_veto 接线门禁。

两条都是"构造违规必响 + 移除触发条件必沉默"的形态；
另含两条真仓库零假设（当前树必须干净，否则说明有人已经越线）。
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.dead_rule_scan import REQUIRED_BUCKETS, assert_buckets_exist

from app_zeri.lint_static import check_demo_veto_wiring


def _full_buckets() -> SimpleNamespace:
    """携带全部必需桶的最小结果对象。"""
    return SimpleNamespace(**{b: [] for b in REQUIRED_BUCKETS})


class TestBucketGuard:
    """dead_rule_scan 的桶白名单：getattr 兜底换来的静默空，必须由这里补回硬失败。"""

    def test_full_buckets_pass(self) -> None:
        assert_buckets_exist(_full_buckets())  # 不抛即通过

    def test_missing_bucket_raises_loudly(self) -> None:
        res = _full_buckets()
        del res.reference  # 模拟引擎重构删桶/改名
        with pytest.raises(RuntimeError, match="reference"):
            assert_buckets_exist(res)

    def test_real_schoolresult_has_all_buckets(self) -> None:
        """真仓库零假设：引擎的 SchoolResult 必须携带全部必需桶。

        若未来有人改了 SchoolResult 而没同步 REQUIRED_BUCKETS，
        这条会在单元测试层先红，不必等到跑完整扫描才发现。
        """
        from core_eval.engine import SchoolResult

        field_names = {f.name for f in dataclasses.fields(SchoolResult)}
        missing = [b for b in REQUIRED_BUCKETS if b not in field_names]
        assert not missing, f"SchoolResult 缺少必需桶 {missing}，请同步 REQUIRED_BUCKETS"


class TestDemoVetoWiring:
    """联调开关只允许 CLI 传参与测试显式构造，环境变量/配置默认值两条路全部封死。"""

    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / "core-eval" / "src").mkdir(parents=True)
        (tmp_path / "app-zeri" / "src").mkdir(parents=True)
        (tmp_path / "core-rule" / "config").mkdir(parents=True)
        return tmp_path

    def test_env_read_is_rejected(self, tmp_path: Path) -> None:
        root = self._repo(tmp_path)
        (root / "app-zeri/src/wiring.py").write_text(
            "import os\nDEMO = os.getenv('DEMO_VETO', '0')\n", encoding="utf-8"
        )
        msgs = check_demo_veto_wiring(root)
        assert len(msgs) == 1
        assert "环境变量" in msgs[0]

    def test_environ_get_is_rejected(self, tmp_path: Path) -> None:
        root = self._repo(tmp_path)
        (root / "app-zeri/src/wiring.py").write_text(
            "import os\nDEMO = os.environ.get('demo-veto')\n", encoding="utf-8"
        )
        msgs = check_demo_veto_wiring(root)
        assert len(msgs) == 1
        assert "environ.get" in msgs[0]

    def test_environ_subscript_is_rejected(self, tmp_path: Path) -> None:
        """os.environ["DEMO-VETO"] 走 Subscript，同样是环境变量通路，一并封死。"""
        root = self._repo(tmp_path)
        (root / "app-zeri/src/wiring.py").write_text(
            "import os\nDEMO = os.environ['DEMO-VETO']\n", encoding="utf-8"
        )
        msgs = check_demo_veto_wiring(root)
        assert len(msgs) == 1
        assert "environ[" in msgs[0]

    def test_unrelated_env_read_is_silent(self, tmp_path: Path) -> None:
        root = self._repo(tmp_path)
        (root / "app-zeri/src/other.py").write_text(
            "import os\nTZ = os.getenv('TZ', 'Asia/Shanghai')\n", encoding="utf-8"
        )
        assert check_demo_veto_wiring(root) == []

    def test_config_yaml_key_is_rejected(self, tmp_path: Path) -> None:
        root = self._repo(tmp_path)
        (root / "core-rule/config/eval.yaml").write_text(
            "demo_veto: true\nallow_unverified: false\n", encoding="utf-8"
        )
        msgs = check_demo_veto_wiring(root)
        assert len(msgs) == 1
        assert "配置文件" in msgs[0]

    def test_real_repo_is_clean(self) -> None:
        root = Path(__file__).resolve().parents[2]
        assert check_demo_veto_wiring(root) == []


class TestDemoVetoBanner:
    """报告横幅：demo_veto=True 必须显眼（首行），False 必须不出现。"""

    def _render(self, demo_veto: bool) -> str:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from app_zeri.report import render_markdown
        from app_zeri.schemas import PersonSpec, SiteSpec, TaskSpec
        from app_zeri.verifier import verify

        result = verify(
            dt=datetime(2027, 7, 11, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            allow_unverified=True,
            demo_veto=demo_veto,
        )
        return render_markdown(result)

    def test_banner_present_when_on(self) -> None:
        text = self._render(True)
        assert "🚧" in text
        assert "演示否决" in text
        assert "不可作为发布依据" in text
        # 横幅必须是显眼的，不许藏进 explain：它出现在报告正文第一行之前
        assert text.index("🚧") < text.index("候选时刻")

    def test_banner_absent_when_off(self) -> None:
        assert "演示否决" not in self._render(False)
