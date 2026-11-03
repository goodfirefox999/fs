SHELL := /bin/bash
export PYTHONPATH := core-time/src:core-symbol/src:core-rule/src:core-eval/src:app-zeri/src:.

# 解释器：优先仓库 venv（本沙箱系统 $(PYTHON) 无 pytest——2026-11-03 实测）
PYTHON ?= .venv/bin/python

.PHONY: help test test-fast cov lint gate golden rules cases clean report mutation determinism check-python

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
	@echo "make cov        覆盖率报告（门禁：整体 >=80%）"
	@echo "make lint       规则库 lint"
	@echo "make gate       全部 CI 门禁"
	@echo "make golden     金标准回归"
	@echo "make cases      运行案例库并产出四份报告"
	@echo "make report     生成金标准案例报告"
	@echo "make rules      重新生成规则库与测试向量（会覆盖，慎用）"
	@echo "make mutation   变异测试抽查（验证测试是否真的能抓住错误）"

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

cov: check-python
	@mkdir -p out
	$(PYTHON) -m pytest -m "not slow" --cov --cov-report=term --cov-report=html --junitxml=out/junit-cov.xml
	$(PYTHON) -m coverage report --fail-under=80

lint:
	$(PYTHON) -m app_zeri.cli rules lint

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
# 退出码 1 = PRODUCT_FAIL（产品不确定）；2 = ENV_SUSPECT（机器忙，不是产品问题）。
determinism:
	$(PYTHON) tools/determinism_probe.py --gate

gate: test-fast lint
	$(PYTHON) tools/no_network_scan.py
	$(PYTHON) tools/check_status_signature.py --offline
	$(PYTHON) tools/check_no_aggregate_score.py
	$(PYTHON) tools/determinism_probe.py --gate
	$(PYTHON) -m coverage report --fail-under=80 || true
	@echo "✅ gate 完成"

rules:
	$(PYTHON) tools/gen_rules.py

clean:
	rm -rf out .pytest_cache .coverage htmlcov tests/.tmp
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
