# -*- coding: utf-8 -*-
"""Phase 1a 回归：四余排除、paywalled 回写、section_order、报告自检。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src.extract_bearing import _is_astro_label, extract_bearings  # noqa: E402
from src.config import DownloadStatus  # noqa: E402
from typing import get_args  # noqa: E402


@pytest.mark.parametrize("label", ["罗", "计", "孛", "气", "罗睺", "计都", "紫气", "月孛", "日", "月", "金", "水"])
def test_four_remainders_are_astro(label):
    assert _is_astro_label(label), f"{label} 应识别为七政四余缠度"


@pytest.mark.parametrize("text", ["罗丑21度", "计未21度", "孛寅10度", "气卯5度"])
def test_four_remainders_not_extracted_as_bearing(text):
    assert extract_bearings(text) == [], f"{text} 不得抽成方位观测"


@pytest.mark.parametrize("text,shan,deg", [
    ("碑坐寅山66度", "寅", 66.0),
    ("朝山：申246度", "申", 246.0),
    ("内水口出：酉266度", "酉", 266.0),
])
def test_real_bearings_survive(text, shan, deg):
    obs = extract_bearings(text)
    assert any(o.shan24 == shan and o.degree == deg for o in obs), f"{text} 应被抽出"


def test_download_status_covers_runtime_values():
    args = get_args(DownloadStatus)
    assert "DEAD" in args and "EXTERNAL_UNAVAILABLE" in args


def test_report_success_count_extraction():
    """报告自检依赖能稳定从文本中提取「成功 N」。"""
    from src.pipeline import _report_success_count

    assert _report_success_count("- 目标帖数: 74459（成功 5417 / 失败 140）") == 5417
    assert _report_success_count("成功 0 / 失败 0") == 0
    assert _report_success_count("没有成功计数字样") is None
