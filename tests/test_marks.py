# -*- coding: utf-8 -*-
"""T7.4 标注色分割回归测试（离线）。

`tid163913_p1_marks.jpg` 是基准帖 tid=163913 第 1 页的原图，作者在上面画了
「父母山」文字 + 「穴星」细椭圆圈 + 一个小号穴位圈 + 沅江青线。用它钉住这几条：

- 1 px 细椭圆必须还能判成 ring。曾因黄色掩膜做 3x3 开运算，整圈被抹掉，黄圈数全为 0。
- 环内文字（"穴星"）不能顶掉环，也不能另算一个标注。
- 线坐标必须是图像坐标。曾用 bbox 局部坐标，沅江 5 段全叠在画面左上角。
- 青线色域要收紧到 S>130。原 S>80 时山脊与天空交界的青灰雾霭会被当成水系线。

`watermark_tiled.jpg` 是论坛水印图（"龍行天下風水論壇"每字套一个小黄圈），
用来钉住"水印不能算穴位圈"。
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import marks  # noqa: E402

FIX = Path(__file__).parent / 'fixtures'
BASE = FIX / 'tid163913_p1_marks.jpg'
WATERMARK = FIX / 'watermark_tiled.jpg'


def _rings(res: dict) -> list[dict]:
    return [f for f in res['features']
            if f['color'] == 'yellow' and f['properties'].get('shape') == 'ring'
            and f['properties']['zone'] == 'content']


def test_baseline_ring_count() -> None:
    """基准图上有两个黄圈：62 px 的「穴星」椭圆 + 14 px 的小穴位圈。"""
    res = marks.analyze(BASE)
    rings = _rings(res)
    assert res['counts']['yellow'] == 2, res['counts']
    assert len(rings) == 2
    assert sorted(f['properties']['diameter_px'] for f in rings) == [14, 62]


def test_baseline_ring_coordinates() -> None:
    """环质心必须落在图像坐标里（曾因 bbox 局部坐标落到左上角）。"""
    res = marks.analyze(BASE)
    pts = [f['geometry']['coordinates'] for f in _rings(res)]
    assert any(abs(x - 916) < 8 and abs(y - 246) < 8 for x, y in pts), pts   # 穴星大椭圆
    assert any(abs(x - 919) < 8 and abs(y - 385) < 8 for x, y in pts), pts   # 小穴位圈


def test_baseline_label_inside_ring_not_double_counted() -> None:
    """圈里的"穴星"两字归给环，不另出一个标注。"""
    res = marks.analyze(BASE)
    assert res['extra']['yellow_nonring'] == 1, res['extra']   # 只剩"父母山"一条文字串


def test_baseline_cyan_lines_trace_river() -> None:
    """沅江 5 段青线：数量对，且都在画面下半部（河在下方）。"""
    res = marks.analyze(BASE)
    assert res['counts']['cyan'] == 5, res['counts']
    for f in res['features']:
        if f['color'] == 'cyan' and f['kind'] == 'line':
            ys = [p[1] for p in f['geometry']['coordinates']]
            assert min(ys) > res['height'] * 0.5, (min(ys), res['height'])


def test_watermark_not_counted_as_rings() -> None:
    """平铺水印的每个小黄圈都不能算穴位圈。"""
    res = marks.analyze(WATERMARK)
    assert res['counts']['yellow'] == 0, (res['counts'], res['extra'])
    # 水印字圈有的走 watermark 标记、有的直接被线宽判据挡掉，两种都算过
    assert not [f for f in res['features']
                if f['properties'].get('shape') == 'ring'
                and f['properties']['zone'] == 'content'], res['extra']


def _scene() -> np.ndarray:
    rng = np.random.default_rng(7)
    bgr = np.zeros((400, 600, 3), np.uint8)
    bgr[..., 0] = 60 + rng.integers(0, 30, (400, 600))
    bgr[..., 1] = 110 + rng.integers(0, 30, (400, 600))
    bgr[..., 2] = 70 + rng.integers(0, 30, (400, 600))
    return bgr


def test_solid_blob_is_not_ring() -> None:
    """实心黄块（稻田/色斑）不是环。"""
    img = _scene()
    cv2.circle(img, (300, 200), 26, (0, 255, 255), -1)
    p = Path('/tmp/_marks_blob.jpg')
    cv2.imwrite(str(p), img)
    assert marks.analyze(p)['counts']['yellow'] == 0


def test_text_run_is_not_ring() -> None:
    """成串同色字＝标题/地名，不算穴位圈。"""
    img = _scene()
    for i, ch in enumerate('ABCD'):
        cv2.putText(img, ch, (200 + i * 26, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    p = Path('/tmp/_marks_text.jpg')
    cv2.imwrite(str(p), img)
    res = marks.analyze(p)
    assert res['counts']['yellow'] == 0, res['counts']
    assert res['extra']['text_runs'] >= 1, res['extra']


def test_geojson_metadata() -> None:
    gj = marks.to_geojson(marks.analyze(BASE), str(BASE))
    assert gj['properties']['georeferenced'] is False
    assert gj['properties']['width_px'] == 1200
    assert gj['features']


def test_thick_stroke_is_not_ring() -> None:
    """粗笔画画的圈不是手绘标注：金色装饰圆/水印字圈线宽 2.7~7.5 px，真标注只有 1.3~1.5 px。"""
    img = _scene()
    cv2.ellipse(img, (300, 200), (30, 26), 0, 0, 360, (0, 255, 255), 5)
    p = Path('/tmp/_marks_thick.jpg')
    cv2.imwrite(str(p), img)
    assert marks.analyze(p)['counts']['yellow'] == 0


def test_bottom_center_band_only_affects_yellow() -> None:
    """画面下方居中的判定只作用于黄色点，沅江青线不能被误判成水印。"""
    res = marks.analyze(BASE)
    # 基准图的青线整条在画面下半部，仍应计 5 条
    assert res['counts']['cyan'] == 5
    for f in res['features']:
        if f['color'] == 'cyan':
            assert f['properties']['zone'] == 'content'
