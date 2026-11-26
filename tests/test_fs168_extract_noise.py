"""fs168 结构化抽取的教程散文噪声过滤（2026-11-26，v3 N-08/N-12 关联）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.fs168_extract import _is_bearing_context  # noqa: E402


class _Obs:
    def __init__(self, label: str, raw: str, shan24: str | None = None):
        self.label = label
        self.raw_text = raw
        self.shan24 = shan24


def test_tutorial_prose_noise_filtered() -> None:
    assert not _is_bearing_context(_Obs("判断罗盘每山", "如何判断罗盘每山的度数"))
    assert not _is_bearing_context(_Obs("每个字向方位角", "每个字向方位角是固定的"))
    assert not _is_bearing_context(_Obs("所以每山相距", "所以每山相距15度"))
    assert not _is_bearing_context(_Obs("有相同五个小格一个山的范围有", "有相同五个小格一个山的范围有15度"))


def test_real_observations_still_pass() -> None:
    assert _is_bearing_context(_Obs("碑坐", "碑坐寅山66度", shan24="寅"))
    assert _is_bearing_context(_Obs("甲方", "甲方120度"))
    assert _is_bearing_context(_Obs("水口", "水口出酉266度"))
