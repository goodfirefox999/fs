"""图片资产：登记（无需授权）+ 图注配对 + 门控下载（默认关闭）。

实测结构（文档 §1.1）：
  <span id="att_{aid}">
    <b>01，无人机看来龙</b><br>
    <img src=".../attachment/thumb/Mon_2610/58_1_{hash}.jpg" border="0"
         onclick=" window.open('.../attachment/Mon_2610/58_1_{hash}.jpg');"
         onload="if(this.width>'700')this.width='700';..." title="Click Here To EnLarge">
  </span>
图注语义：图前一行编号说明（att span 内首个 <b>）+ 图后一段详细描述（span 之后文本）。
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 附件容器有两种写法（2026-11-16 实测）：
#   新模板 <span id="att_{aid}">…</span>（在正文 div 内）
#   老模板 <div style="margin:5px 0;" id="att_{aid}">…</div>（在正文 div 之前）
# 老写法此前完全漏抽，是「有图帖零图片记录」的主因。div 容器实测均只含 1 张图且无嵌套 div，
# 非贪婪 </div> 安全。
ATT_SPAN = re.compile(r'<(span|div)[^>]*\bid="att_(\d+)"[^>]*>([\s\S]*?)</\1>', re.I)
HIDDEN_SPAN = re.compile(r'<span[^>]*display\s*:\s*none[^>]*>[\s\S]*?</span>', re.I)
IMG_SRC = re.compile(r'<img[^>]*\bsrc="([^"]+)"', re.I)
ONCLICK_FULL = re.compile(r"window\.open\('([^']+)'\)")
ATT_PATH = re.compile(r"/attachment/(?:thumb/)?(.+?)(?:\?|$)")
BOLD = re.compile(r"<b[^>]*>([\s\S]*?)</b>", re.I)


def image_id_from_path(path: str) -> str:
    """'Mon_2610/58_1_61e1c1ae4b410cf.jpg' -> '58_1_61e1c1ae4b410cf'"""
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0]


def normalize_img_src(src: str) -> str:
    """老帖部分 `<img src="attachment/upload/67.jpg">` 缺前导斜杠。

    缺斜杠时 `/attachment/` 判定不成立，整张图被当作「表情/UI 图标」丢弃
    （实测 fid=24 老模板 400 个归档目录里 7,705 处）。归一化后重新判定。
    """
    s = src.strip()
    if s.lower().startswith("attachment/"):
        return "/" + s
    return s


@dataclass
class ImageRef:
    image_id: str
    tid: int
    pid: str
    fid: int
    author_uid: int
    position_index: int
    thumb_url: str
    full_url: str
    caption_before: str = ""
    caption_after: str = ""
    download_status: str = "PENDING"
    aid: str | None = None


@dataclass
class ImageRegistry:
    """clean.py 回调用的登记表：把 <img> 替换为与 att 提取对齐的占位符。

    refs 为 extract_att_images() 的产出（权威 position_index）；
    表情等非 attachment 图片直接丢弃；未匹配的 attachment 图片追加为新 ref。
    """

    tid: int
    pid: str
    fid: int
    author_uid: int
    refs: list[ImageRef] = field(default_factory=list)
    _extra_seq: int = 0

    def _url_key(self, url: str) -> str:
        m = ATT_PATH.search(url)
        return m.group(1) if m else url

    def register(self, img_tag_html: str) -> str:
        m_src = IMG_SRC.search(img_tag_html)
        if not m_src:
            return ""
        src = normalize_img_src(m_src.group(1))
        if "/attachment/" not in src:
            return ""  # 表情图标等：从语料中丢弃
        key = self._url_key(src)
        for ref in self.refs:
            if key in (self._url_key(ref.thumb_url), self._url_key(ref.full_url)):
                return f"\n[[IMG:{ref.position_index}:{ref.image_id}]]\n"
        # 罕见：att 容器之外的附件图 → 追加
        self._extra_seq += 1
        if "/thumb/" in src:
            full_url = src.replace("/thumb/", "/")
        else:
            full_url = src
        ref = ImageRef(
            image_id=image_id_from_path(key),
            tid=self.tid,
            pid=self.pid,
            fid=self.fid,
            author_uid=self.author_uid,
            position_index=len(self.refs) + 1,
            thumb_url=src if "/thumb/" in src else "",
            full_url=full_url,
        )
        self.refs.append(ref)
        return f"\n[[IMG:{ref.position_index}:{ref.image_id}]]\n"


def extract_att_images(page_html: str, tid: int, pid: str, fid: int,
                       author_uid: int, content_start: int, content_end: int,
                       scan_start: int | None = None) -> list[ImageRef]:
    """从楼层内容区提取 att 容器图片：thumb/full 分离 + 图前图注。

    content_start/end 为该楼层内容 div 在 page_html 中的字符区间，
    caption_after 取到下一个 att span 或区间尾（截 300 字）。

    scan_start：附件容器可能整体位于正文 div **之前**（老模板
    `<div id="att_N">` 在 `<div class="f14" id="read_tpc">` 前面），
    因此扫描区要往前扩到上一层正文结束处。为免误吞上一层的附件，
    只保留紧邻本层（距正文开头 ≤4000 字符）的容器。
    """
    span_re = ATT_SPAN
    refs: list[ImageRef] = []
    seq = 0
    scan_from = content_start if scan_start is None else max(0, min(scan_start, content_start))
    spans = [
        (m.start(), m.end(), m.group(2), m.group(3))
        for m in span_re.finditer(page_html, scan_from, content_end)
    ]
    spans = [
        s for s in spans
        if s[0] >= content_start or (content_start - s[1]) <= 4000
    ]
    for k, (s, e, aid, inner) in enumerate(spans):
        m_src = IMG_SRC.search(inner)
        if not m_src:
            continue
        src = normalize_img_src(m_src.group(1))
        if "/attachment/" not in src:
            continue    # zip/torrent 等文件附件的 UI 图标（images/wind/file/*），非图片资产
        m_att = ATT_PATH.search(src)
        path = m_att.group(1) if m_att else src
        m_full = ONCLICK_FULL.search(inner)
        if "/thumb/" in src:
            full_from_thumb = src.replace("/thumb/", "/")
        else:
            full_from_thumb = src
        full_url = m_full.group(1) if m_full else full_from_thumb
        m_b = BOLD.search(inner)
        caption_before = ""
        if m_b:
            caption_before = _html.unescape(re.sub(r"<[^>]+>", "", m_b.group(1))).strip()
        else:
            # 老模板 div 容器没有 <b>，图前注是纯文本（实测多为「图片：」）。
            pre = re.sub(r"<[^>]+>", " ", inner.split("<img", 1)[0])
            pre = re.sub(r"\s+", " ", _html.unescape(pre)).strip()
            caption_before = "" if pre in ("", "图片", "图片：", "图片:") else pre[:60]
        if k + 1 < len(spans):
            next_start = spans[k + 1][0]
        else:
            # 容器在正文 div 之前时，尾部不能越界到正文里（会把整段正文当图注）。
            bound = content_start if e <= content_start else content_end
            next_start = min(bound, e + 600)
        next_start = max(next_start, e)
        after_raw = page_html[e:next_start]
        after_raw = HIDDEN_SPAN.sub("", after_raw)      # 反采集水印不得混入图注
        caption_after = re.sub(r"<[^>]+>", " ", after_raw)
        caption_after = _html.unescape(caption_after)
        caption_after = re.sub(r"\s+", " ", caption_after).strip()[:300]
        seq += 1
        refs.append(
            ImageRef(
                image_id=image_id_from_path(path),
                tid=tid,
                pid=pid,
                fid=fid,
                author_uid=author_uid,
                position_index=seq,
                thumb_url=src if "/thumb/" in src else "",
                full_url=full_url,
                caption_before=caption_before,
                caption_after=caption_after,
                aid=aid,
            )
        )
    return refs


def download_images(
    refs: list[ImageRef], images_dir: Path, session: Any,
    max_concurrent: int = 3,
) -> None:
    """门控下载（仅 image_download_approved=true 时由 pipeline 调用）。

    full 优先，404 回退 thumb；Pillow 校验 + sha256；遵守全局令牌桶。
    简单顺序实现 + 令牌桶限速即满足 ≤3 并发约束（顺序=并发1，恒合规）。
    """
    from PIL import Image  # 局部导入：仅在授权下载时需要

    images_dir.mkdir(parents=True, exist_ok=True)
    for ref in refs:
        tid_dir = images_dir / str(ref.tid)
        tid_dir.mkdir(parents=True, exist_ok=True)
        dest = tid_dir / f"{ref.position_index:02d}_{ref.image_id}.jpg"
        ok = False
        for url in (ref.full_url, ref.thumb_url):
            if not url:
                continue
            try:
                result = session.get_bytes(url)
                if result.status != 200 or len(result.body) < 1000:
                    continue
                dest.write_bytes(result.body)
                with Image.open(dest) as im:
                    im.verify()
                ok = True
                break
            except Exception:
                continue
        if ok:
            data = dest.read_bytes()
            ref.download_status = "DONE"
            ref.sha256 = hashlib.sha256(data).hexdigest()  # type: ignore[attr-defined]
            ref.local_path = str(dest)  # type: ignore[attr-defined]
        else:
            ref.download_status = "FAILED"
            dest.unlink(missing_ok=True)


def export_meta_json(ref: ImageRef, extra: dict[str, Any], dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "image_id": ref.image_id,
        "tid": ref.tid,
        "pid": ref.pid,
        "position_index": ref.position_index,
        "thumb_url": ref.thumb_url,
        "full_url": ref.full_url,
        "caption_before": ref.caption_before,
        "caption_after": ref.caption_after,
        **extra,
    }
    (dest_dir / "meta.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
