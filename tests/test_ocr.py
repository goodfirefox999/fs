# -*- coding: utf-8 -*-
"""§7.4 ocr.json：预处理、TSV 解析、端到端（无 tesseract 时自动跳过）。"""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import ocr  # noqa: E402

FONT = "/System/Library/Fonts/Supplemental/Songti.ttc"


def test_yellow_text_image_keeps_only_yellow() -> None:
    """预处理只留黄色墨迹，且输出是黑字白底（tesseract 偏好深字浅底）。"""
    img = np.full((80, 200, 3), 60, np.uint8)          # 深绿底
    cv2.line(img, (10, 40), (190, 40), (0, 255, 255), 3)   # 黄线
    out = ocr._yellow_text_image(img)
    dark = (out < 128)
    assert dark.sum() > 100                            # 黄线被保留成黑
    assert out[0, 0] > 200                             # 背景变白


def test_parse_tsv_filters_low_conf_and_scales() -> None:
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t100\t50\t40\t30\t92.5\t来水\n"
        "5\t1\t1\t1\t1\t2\t200\t50\t40\t30\t20.0\t噪声\n"
        "5\t1\t1\t1\t1\t3\t300\t50\t40\t30\t88.0\t\n"
    )
    words = ocr._parse_tsv(tsv, scale=2.0)
    assert [w["text"] for w in words] == ["来水"]
    assert words[0]["bbox"] == [50, 25, 70, 40]        # 坐标按 scale 还原


def test_to_json_shape() -> None:
    doc = {"engine": "x", "size": [10, 20], "text": "abc",
           "words": [{"text": "a", "conf": 90.0, "bbox": [0, 0, 1, 1]}]}
    j = ocr.to_json(doc, "a.jpg")
    assert j["source_image"] == "a.jpg"
    assert j["coordinate_origin"] == "top-left"
    assert j["words"][0]["text"] == "a"


@pytest.mark.skipif(not (ocr.available() and Path(FONT).exists()),
                    reason="需要 tesseract + chi_sim + 系统中文字体")
def test_ocr_reads_large_chinese() -> None:
    """25px 以上的标注文字要能读出来（圈内 15px 小字读不出，见模块 docstring）。"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (520, 140), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 48)
    d.text((20, 40), "来水 313度", font=f, fill=(255, 210, 0))   # RGB 黄，走黄色掩膜
    tmpdir = Path(__file__).parent / "_tmp_ocr"
    tmpdir.mkdir(parents=True, exist_ok=True)
    p = tmpdir / "_ocr_case.png"
    img.save(p)
    doc = ocr.ocr_image(p)
    assert doc["words"], doc
    assert "313" in doc["text"], doc["text"]
