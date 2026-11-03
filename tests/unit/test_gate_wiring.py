"""``make gate`` 的接线锁（2026-11-03 评审九回路）。

事故：``gate`` 只跑 ``test-fast``（不采集覆盖率），然后 ``coverage report``
读上一次遗留的 ``.coverage``，报出 75%；再跟 ``|| true``，覆盖率门禁名存实亡。
fresh ``make cov`` 实测 84%——75% 是旧数据，不是当前代码。

本文件锁住三件事，防止接线被改回去：

1. ``gate`` 依赖 ``cov``（pytest --cov 新鲜采集），不再依赖不采覆盖率的 ``test-fast``；
2. ``coverage report --fail-under=80`` 不得跟 ``|| true``；
3. CI 中确定性门禁只能走 ``tools/determinism_gate.py``，``make determinism``
   在 ``CI=true`` 时必须拒绝。
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MAKEFILE = (_ROOT / "Makefile").read_text(encoding="utf-8")
_CI = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _target(name: str) -> tuple[list[str], list[str]]:
    """返回 (依赖列表, recipe 行列表)；找不到目标直接失败。"""
    lines = _MAKEFILE.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(f"{name}:"):
            deps = line.split(":", 1)[1].split()
            recipe: list[str] = []
            for following in lines[index + 1 :]:
                if not following.startswith("\t"):
                    break
                recipe.append(following[1:])
            return deps, recipe
    raise AssertionError(f"Makefile 缺少目标 {name}")


def test_gate_uses_fresh_coverage_not_test_fast() -> None:
    deps, _ = _target("gate")
    assert "cov" in deps, "gate 必须依赖 cov，由 pytest --cov 新鲜写 .coverage"
    assert "test-fast" not in deps, "test-fast 不采集覆盖率，不能作为 coverage report 的数据源"


def test_cov_collects_then_enforces_threshold() -> None:
    _, recipe = _target("cov")
    text = "\n".join(recipe)
    assert "--cov" in text and "pytest" in text, "cov 必须自己采集覆盖率"
    assert "coverage report --fail-under=80" in text, "覆盖率阈值必须由 cov 自己阻断"


def test_cov_enforces_per_module_ratchet() -> None:
    """整体 84% 不能替 app-zeri 68% 背书：cov 必须跑分模块 ratchet。"""
    _, recipe = _target("cov")
    text = "\n".join(recipe)
    assert "tools/coverage_ratchet.py" in text, "cov 必须逐模块检查覆盖率基线"
    assert "|| true" not in text, "ratchet 失败不得被吞掉"
    assert "make cov" in _CI, "CI 必须走 make cov，避免与本地门禁接线漂移"


def test_cov_runs_perf_smoke_without_coverage() -> None:
    """计时断言不能在 coverage 插桩下跑；cov 末尾用独立无插桩进程补一次。"""
    _, recipe = _target("cov")
    text = "\n".join(recipe)
    assert "junit-perf-smoke.xml" in text
    smoke = [line for line in recipe if "test_single_month_budget_smoke" in line]
    assert len(smoke) == 1, "单月冒烟必须在 cov 里恰好跑一次（无插桩）"
    assert "--cov" not in smoke[0], "性能冒烟不得在 coverage 插桩下计时"


def test_cov_runs_smoke_and_ratchet_before_aggregate_exit() -> None:
    """覆盖率红时性能门禁不得静默消失（评审十回路）。

    事故形态：``coverage report`` 失败若直接终止 recipe，末尾的独立冒烟与 ratchet
    根本不会执行——最需要看性能有没有同时退化的时刻，恰恰是它被跳过的时候。
    锁两点：三条判定都在同一个 recipe 里跑完；冒烟先于 ratchet（先拿便宜的性能信号）。
    """
    _, recipe = _target("cov")
    joined = "\n".join(recipe)

    # 三条判定同处一个 shell 段落（以 rc=0 起始），否则前一条失败会掐断后一条
    assert "rc=0" in joined and "exit $$rc" in joined, "cov 必须汇总三项退出码，而不是遇错即停"
    window = joined.split("rc=0", 1)[1]
    for probe in ("coverage report --fail-under=80", "test_single_month_budget_smoke", "tools/coverage_ratchet.py"):
        assert probe in window, f"{probe} 必须在同一个 rc 汇总段里执行"

    # 冒烟先于 ratchet：性能信号不被 ratchet 挡住
    assert window.index("test_single_month_budget_smoke") < window.index("tools/coverage_ratchet.py"), (
        "性能冒烟必须在 ratchet 之前执行，避免 ratchet 红时冒烟静默消失"
    )


def test_coverage_version_is_pinned_where_floor_is_measured() -> None:
    """``floor(实测)`` 零余量成立的前提：CI 与本地是同一 coverage 版本。

    coverage 版本漂移会改变分支计数（0.1–0.3pp 级），零余量地板会在 CI 上假红。
    """
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "coverage==" in pyproject, "coverage 必须锁死到补丁版（分支计数随版本变化）"
    pin = [tok for tok in pyproject.replace('"', " ").replace(",", " ").split() if tok.startswith("coverage==")]
    assert pin, "pyproject 必须显式声明 coverage==<version>"
    version = pin[0].split("==", 1)[1]
    assert f"coverage=={version}" in _CI, f"CI 安装的 coverage 版本必须与 pyproject 一致（{version}）"
    assert "python-version: \"3.14" in _CI, "CI 解释器必须钉到与本地一致的补丁版，不能用 3.14 漂移"


def test_mutation_report_default_goes_to_out_not_docs() -> None:
    """``make mutation`` 不得自动改 git 里的 docs/：否则时间戳污染提交（同 bench_history）。"""
    _, recipe = _target("mutation")
    text = "\n".join(recipe)
    assert "docs/mutation-report.md" not in text, "make mutation 不得默认写 docs/（运行产物应进 out/）"
    source = (_ROOT / "tools" / "mutation_check.py").read_text(encoding="utf-8")
    assert '"out" / "mutation-report.md"' in source, "mutation_check 默认报告路径必须是 out/mutation-report.md"
    assert "out/" in (_ROOT / ".gitignore").read_text(encoding="utf-8"), "out/ 必须在 .gitignore 里"


def test_ci_runs_on_verification_branches() -> None:
    """推 ``ci/verify-py314`` 必须能自动触发 CI（评审十回路）。

    Action 只挂 ``main/master`` 时，推验证分支不会跑任何东西——「推临时分支实测
    Python 3.14.2」这个唯一阻塞项就变成了空操作，而人看到的是「推上去了」。
    """
    assert "ci/**" in _CI, "CI 必须监听 ci/** 验证分支，否则推分支验不到任何东西"
    assert "workflow_dispatch" in _CI, "CI 应可从 UI 手动触发（补跑/复验）"


def test_ci_records_perf_smoke_seconds() -> None:
    """3.0s 档只有 0.38s 余量：每次实测要落 artifact，连续超档要提前告警。"""
    assert "perf_smoke_record.py" in _CI, "CI 必须记录性能冒烟实测耗时"
    assert "perf-smoke.jsonl" in _CI, "耗时样本必须进 artifact（否则观察不到趋势）"
    assert "--warn-above 2.5" in _CI, "观察档应在 2.5s 提前告警，而不是等 3.0s 红"


def test_coverage_failure_is_never_swallowed() -> None:
    _, gate_recipe = _target("gate")
    assert "|| true" not in "\n".join(gate_recipe), "gate 不得吞掉任何失败"
    for line in _MAKEFILE.splitlines():
        if "coverage report" in line:
            assert "|| true" not in line, f"覆盖率门禁不得被 || true 吞掉：{line.strip()}"


def test_determinism_refuses_direct_ci_call() -> None:
    _, recipe = _target("determinism")
    text = "\n".join(recipe)
    assert "CI" in text and "exit 64" in text, "CI=true 时 make determinism 必须拒绝运行"
    assert "make gate" in text, "拒绝信息必须指向唯一 CI 入口 make gate"


def test_ci_determinism_step_uses_adapter_only() -> None:
    assert "tools/determinism_gate.py" in _CI
    assert "make determinism" not in _CI, "CI 不得直接调用会绕过适配层的 make determinism"
    assert "determinism_probe.py --gate" not in _CI, "CI 不得直接调用原始探针"
