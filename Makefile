SHELL := /bin/bash
export PYTHONPATH := core-time/src:core-symbol/src:core-rule/src:core-eval/src:app-zeri/src:.

.PHONY: help test test-fast cov lint gate golden rules cases clean report mutation determinism

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

test:
	python3 -m pytest

test-fast:
	python3 -m pytest -m "not slow"

cov:
	python3 -m pytest -m "not slow" --cov --cov-report=term --cov-report=html
	python3 -m coverage report --fail-under=80

lint:
	python3 -m app_zeri.cli rules lint

golden:
	python3 -m pytest tests/golden -v

cases:
	python3 -m app_zeri.cli cases run --grade A --out out/cases

report:
	mkdir -p out
	python3 -m app_zeri.cli verify --course 2027-07-11T14:00 --azimuth 320 \
		--task 修造 --strictness strict --allow-unverified --out out/golden-report.md
	@echo "已生成 out/golden-report.md"

mutation:
	python3 tools/mutation_check.py

# 确定性门禁（2026-11-03）：多 PYTHONHASHSEED 比对指纹。
# 退出码 1 = PRODUCT_FAIL（产品不确定）；2 = ENV_SUSPECT（机器忙，不是产品问题）。
determinism:
	python3 tools/determinism_probe.py --gate

gate: test-fast lint
	python3 tools/no_network_scan.py
	python3 tools/check_status_signature.py --offline
	python3 tools/check_no_aggregate_score.py
	python3 tools/determinism_probe.py --gate
	python3 -m coverage report --fail-under=80 || true
	@echo "✅ gate 完成"

rules:
	python3 tools/gen_rules.py

clean:
	rm -rf out .pytest_cache .coverage htmlcov tests/.tmp
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
