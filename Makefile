SHELL := /bin/bash
export PYTHONPATH := core-time/src:core-symbol/src:core-rule/src:core-eval/src:app-zeri/src:.

# 解释器：优先仓库 venv（本沙箱系统 $(PYTHON) 无 pytest——2026-11-03 实测）
PYTHON ?= .venv/bin/python

.PHONY: help test test-fast cov lint gate golden rules cases clean report mutation determinism determinism-gate check-yaml check-proxy push check-python

# 解释器预检（2026-11-03）：.venv 不存在时 make 只会甩 ModuleNotFoundError，
# 看不出"该建 venv"。这里前置断言，给出可直接粘贴的命令。
# 用 `$(shell)` 在解析期求值，避免每个目标各写一遍 recipe。
PYTEST_OK := $(shell $(PYTHON) -c "import pytest" >/dev/null 2>&1 && echo 1)

check-python:
	@if [ -z "$(PYTEST_OK)" ]; then \
		echo "❌ 解释器不可用或缺少 pytest：$(PYTHON)"; \
		echo "   首次运行请先建 venv："; \
		echo "     python3 -m venv .venv && .venv/bin/pip install -e '.[dev,astro]'"; \
		echo "   或指定解释器：make test PYTHON=/path/to/python"; \
		exit 1; \
	fi


help:
	@echo "make test       全量测试（含性能）"
	@echo "make test-fast  跳过 slow 标记"
	@echo "make cov        覆盖率报告（新鲜采集，门禁：整体 >=80% + 包级/文件级 ratchet）"
	@echo "make lint       规则库 lint"
	@echo "make check-yaml 校验 .github/workflows/*.yml 语法"
	@echo "make gate       全部 CI 门禁（check-yaml + cov + lint + ...）"
	@echo "make golden     金标准回归"
	@echo "make cases      运行案例库并产出四份报告"
	@echo "make report     生成金标准案例报告"
	@echo "make rules      重新生成规则库与测试向量（会覆盖，慎用）"
	@echo "make mutation   变异测试抽查（验证测试是否真的能抓住错误）"
	@echo "make determinism 确定性探针（原始退出码：3 = OUTPUT_FAIL，仍返回 3）"
	@echo "make determinism-gate 确定性门禁 CI 适配层（只把 3 降级为带警告通过）"
	@echo "make check-proxy push 前代理预检（区分环境变量丢失 vs 上游故障）"
	@echo "make push       代理预检后 git push"

# 2026-11-03：junitxml 默认化（AGENTS 环境事实第 10 条）——本沙箱 pytest 的 stdout
# 汇总行不可见，报数的唯一权威来源是 XML；每次测试收尾用 summarize_junit.py 打标准行。
test: check-python
	@mkdir -p out
	$(PYTHON) -m pytest --junitxml=out/junit-full.xml
	@$(PYTHON) tools/summarize_junit.py out/junit-full.xml

test-fast: check-python
	@mkdir -p out
	$(PYTHON) -m pytest -m "not slow" --junitxml=out/junit-fast.xml
	@$(PYTHON) tools/summarize_junit.py out/junit-fast.xml

# 注意：cov 必须由 pytest --cov 新鲜采集 .coverage，再交给 coverage report。
# 2026-11-03 事故：gate 不跑 cov，只读上一次遗留的 .coverage，报出 75%
# （fresh 实测 84%）；再配 `|| true`，覆盖率门禁名存实亡。禁止改回读旧数据。
# 整体 >=80% 之外再跑包级 + 文件级 ratchet（tools/coverage_ratchet.yaml）：
# 整体 84% 掩盖 app-zeri 68%，包级 68% 又掩盖 cli.py 34%；两层地板才堵住。
# 末尾再用无插桩进程跑一次性能冒烟：计时断言在 coverage 下不可比（见该测试注释）。
# 三项判定（覆盖率/性能/ratchet）全部跑完再汇总退出码，避免前者失败让后者静默消失。
cov: check-python
	@mkdir -p out
	$(PYTHON) -m pytest -m "not slow" --cov --cov-report=term --cov-report=html --junitxml=out/junit-cov.xml
	@rc=0; \
	$(PYTHON) -m coverage report --fail-under=80 || rc=1; \
	$(PYTHON) -m pytest tests/golden/test_required_and_negative.py::TestAdr0014EvidenceCap::test_single_month_budget_smoke --junitxml=out/junit-perf-smoke.xml || rc=1; \
	$(PYTHON) tools/summarize_junit.py out/junit-perf-smoke.xml --perf || rc=1; \
	$(PYTHON) tools/coverage_ratchet.py || rc=1; \
	$(PYTHON) tools/summarize_junit.py out/junit-cov.xml; \
	exit $$rc

lint:
	$(PYTHON) -m app_zeri.cli rules lint

check-yaml: check-python
	$(PYTHON) tools/check_yaml.py

golden: check-python
	@mkdir -p out
	$(PYTHON) -m pytest tests/golden --junitxml=out/junit-golden.xml
	@$(PYTHON) tools/summarize_junit.py out/junit-golden.xml

cases:
	$(PYTHON) -m app_zeri.cli cases run --grade A --out out/cases

report:
	mkdir -p out
	$(PYTHON) -m app_zeri.cli verify --course 2027-07-11T14:00 --azimuth 320 \
		--task 修造 --strictness strict --allow-unverified --out out/golden-report.md
	@echo "已生成 out/golden-report.md"

mutation:
	$(PYTHON) tools/mutation_check.py

# 确定性门禁（2026-11-03）：多 PYTHONHASHSEED 比对指纹。
# 退出码 1 = PRODUCT_FAIL（产品不确定）；2 = ENV_SUSPECT（机器忙，不是产品问题）；
# 3 = OUTPUT_FAIL（报告文本不确定）。本目标保留原始退出码，供人工复核。
# CI 中禁止直接调用：否则 3 会绕过 determinism_gate 适配层直接阻断。
# 64 = 调用方式错误（不是产品/环境判定）。
determinism:
	@if [ "$${CI:-}" = "true" ]; then \
		echo "❌ CI 中禁止直接调用 make determinism：它会绕过 OUTPUT_FAIL 适配层。"; \
		echo "   请改用 make gate（内部走 tools/determinism_gate.py）。"; \
		exit 64; \
	fi
	$(PYTHON) tools/determinism_probe.py --gate

# CI 适配层（AGENTS.md 确定性门禁第 15 条）：只把 3 降级成 0 + out/output-fail.flag。
# 1/2 仍阻断；这样「可带警告发布」不会退化成「所有失败都放过」。
determinism-gate:
	$(PYTHON) tools/determinism_gate.py

check-proxy:
	$(PYTHON) tools/check_proxy.py

push: check-proxy
	git push

# 覆盖率必须是本目标刚跑出来的：`cov` 用 pytest --cov 新鲜采集 .coverage，
# 并由 coverage report --fail-under=80 阻断。禁止（a）只读旧 .coverage，
# （b）用 `|| true` 吞掉失败。测试锚点：tests/unit/test_gate_wiring.py。
gate: check-yaml cov lint
	$(PYTHON) tools/no_network_scan.py
	$(PYTHON) tools/check_status_signature.py --offline
	$(PYTHON) tools/check_no_aggregate_score.py
	$(PYTHON) tools/determinism_gate.py
	@if [ -f out/output-fail.flag ]; then \
		echo "⚠️ gate 完成（带 OUTPUT_FAIL 警告：out/output-fail.flag）"; \
	else \
		echo "✅ gate 完成"; \
	fi

rules:
	$(PYTHON) tools/gen_rules.py

clean:
	rm -rf out .pytest_cache .coverage htmlcov tests/.tmp
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
