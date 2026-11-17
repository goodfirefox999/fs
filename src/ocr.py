# -*- coding: utf-8 -*-
"""图上标注文字 OCR（文档 §7.4 的 ocr.json）。

**能力边界（实测，别指望更多）**：
- 标注文字 ≥25 px 时，tessdata_best/chi_sim 能读对（实测「来水：乾方周天313度」整句正确）
- 圈内小字（穴星、①②③，字高 15~20 px）读不出来——二值化后笔画已经糊在一起，
  放大到 8 倍也是乱码。所以**不能**用 OCR 去区分「穴星圈」和「圈数字」。

预处理走黄色掩膜反色（而不是灰度）：本语料标注是纯黄，掩膜把背景整片压掉，
信噪比比灰度图高一个档（实测灰度识别出「半天3曙度」，掩膜能出「来水：乾方周天」）。

用法：
    from .ocr import ocr_image
    doc = ocr_image(Path('x.jpg'))     # -> {'text','words','engine','available'}
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# tessdata_best 比 tessdata_fast 准得多（fast 把"来水"读成"半天"），优先用它
_CANDIDATES = (
    Path.home() / ".local/share/tessdata_best",
    Path.home() / ".local/share/tessdata",
)
MIN_CONF = 45.0
PSM = "6"                      # 单一文本块；sparse(11) 在长标注上会把一行拆碎


def _tessdata_dir() -> Path | None:
    env = os.environ.get("TESSDATA_PREFIX")
    if env and (Path(env) / "chi_sim.traineddata").exists():
        return Path(env)
    for d in _CANDIDATES:
        if (d / "chi_sim.traineddata").exists():
            return d
    return None


def available() -> bool:
    return bool(shutil.which("tesseract")) and _tessdata_dir() is not None


def _yellow_text_image(bgr: np.ndarray) -> np.ndarray:
    """黄色标注 → 黑字白底。掩膜外全部压白，背景干扰直接消失。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    mask = ((h >= 18) & (h <= 38) & (s > 90) & (v > 130)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)))
    inv = 255 - mask
    # 小图放大再识别；大图保持原尺寸（tesseract 对 >2000px 会自己缩放，反而慢）
    scale = 1.0 if max(bgr.shape[:2]) > 1600 else 2.0
    if scale != 1.0:
        inv = cv2.resize(inv, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return inv


def _parse_tsv(tsv: str, scale: float) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for line in tsv.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) < 12 or cols[0] != "5":
            continue
        text = cols[11].strip()
        if not text:
            continue
        try:
            conf = float(cols[10])
            x, y, w, h = (int(cols[i]) for i in (6, 7, 8, 9))
        except ValueError:
            continue
        if conf < MIN_CONF:
            continue
        words.append({"text": text, "conf": round(conf, 1),
                      "bbox": [round(x / scale), round(y / scale),
                               round((x + w) / scale), round((y + h) / scale)]})
    return words


def ocr_image(img_path: Path) -> dict[str, Any]:
    """单图 OCR → {available, engine, size, text, words}。失败不抛，返回空结果。"""
    td = _tessdata_dir()
    out: dict[str, Any] = {"available": bool(shutil.which("tesseract") and td),
                           "engine": "tesseract chi_sim (tessdata_best)" if td else None,
                           "size": None, "text": "", "words": []}
    bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    if bgr is None or not out["available"]:
        return out
    h, w = bgr.shape[:2]
    out["size"] = [int(w), int(h)]
    scale = 1.0 if max(h, w) > 1600 else 2.0
    img = _yellow_text_image(bgr)
    # 没有黄字就直接返回，不启动 tesseract：全站九成图没有标注文字，
    # 省下的进程启动开销比 OCR 本身还多（实测 0.9s → 0.02s）
    if int((img < 128).sum()) < 150:
        out["text"] = ""
        return out

    # 必须写到真实文件：tesseract 在沙箱里读不了 /tmp，且不认 stdin 的 PNG 流
    tmpdir = Path(tempfile.mkdtemp(prefix="ocr_"))
    try:
        src = tmpdir / "in.png"
        cv2.imwrite(str(src), img)
        env = dict(os.environ, TESSDATA_PREFIX=str(td))
        with open(tmpdir / "err.txt", "wb") as err:
            subprocess.run(["tesseract", str(src), str(tmpdir / "out"),
                            "-l", "chi_sim", "--psm", PSM, "tsv"],
                           stdout=err, stderr=err, env=env, timeout=120, check=False)
        tsv_path = tmpdir / "out.tsv"
        if tsv_path.exists():
            out["words"] = _parse_tsv(tsv_path.read_text(encoding="utf-8", errors="ignore"), scale)
        out["text"] = "".join(wd["text"] for wd in out["words"])
    except Exception as exc:                     # OCR 失败不能影响主流程
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return out


def to_json(doc: dict[str, Any], src: str) -> dict[str, Any]:
    return {"source_image": src, "coordinate_origin": "top-left", "coordinate_unit": "px",
            "engine": doc.get("engine"), "size": doc.get("size"),
            "note": "仅图上黄色标注文字；圈内 15~20px 小字识别不可靠，未收录",
            "text": doc.get("text", ""), "words": doc.get("words", [])}
