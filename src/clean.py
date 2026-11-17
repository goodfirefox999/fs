"""正文清洗（文档 T4）：八步顺序不可调换。

验收标准：输出不得含 <、>、this.width、display:none、JS 片段；
图片以 [[IMG:{position_index}:{image_id}]] 占位符内嵌，图文绑定不丢失。
"""
from __future__ import annotations

import html
import re

from .images import ImageRegistry

ONLOAD_ATTR = re.compile(r'\s+on(?:load|click)\s*=\s*"[^"]*"', re.I)
HIDDEN_SPAN = re.compile(r'<span[^>]*style\s*=\s*["\'][^"\']*display\s*:\s*none[^"\']*["\'][^>]*>[\s\S]*?</span>', re.I)
SCRIPT_STYLE = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.I)
IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
BR = re.compile(r"<br\s*/?>", re.I)
BLOCK_END = re.compile(r"</(p|div|li|h[1-6]|tr|table|blockquote)>", re.I)
ANY_TAG = re.compile(r"<[^>]+>")
ONLOAD_FRAGMENT = re.compile(r"'\d+'\)\s*this\.(width|height)\s*=\s*'\d+'[^>\n]*")
ENLARGE_TAIL = re.compile(r"title=\"Click Here To EnLarge\">?")
# 实测坑（2024 前后老帖）：广告 JS 以 HTML 转义文本嵌在正文里（不在 <script> 内），
# 反转义后成为 JS 残片。注入为两段式：__vbox 前导 + (function(){setTimeout...vbox...})() 包装，
# 中途还有裸 })();，非贪婪到 })(); 会提前截断——统一吞到包装尾 }, N);})();。
VBOX_JS = re.compile(
    r"(?:if \(typeof (?:window\.top\.)?__vbox_invoke_ids"
    r"|\(function\(\) \{\s*setTimeout\(function\(\)\{\s*if \(typeof vbox )"
    r"[\s\S]*?\}, \d+\);\}\)\(\);"
)
SPACES = re.compile(r"[ \t\u3000]+")
NEWLINES = re.compile(r"\n{3,}")


def clean_floor_html(raw: str, image_registry: ImageRegistry) -> str:
    """按文档规定的顺序清洗单个楼层 HTML。"""
    s = raw
    # 步骤1：删除反爬混淆 span（必须在抽文本前，否则混入随机字符）
    s = HIDDEN_SPAN.sub("", s)
    # 步骤2：删除 script/style
    s = SCRIPT_STYLE.sub("", s)
    # 步骤3：图片 → 位置占位符（保留图文绑定，同时登记 registry）
    # 3a. 实测坑：onload/onclick 属性内嵌未转义的 '>' 与引号，会使 <img[^>]*>
    #     提前截断并泄漏 JS 碎片——先剥离这两个属性，再做 img 匹配
    s = ONLOAD_ATTR.sub("", s)
    s = IMG_TAG.sub(lambda m: image_registry.register(m.group(0)), s)
    # 步骤4：块级标签 → 换行
    s = BR.sub("\n", s)
    s = BLOCK_END.sub("\n", s)
    # 步骤5：去除全部残余标签
    s = ANY_TAG.sub("", s)
    # 步骤6：HTML 实体反转义
    s = html.unescape(s)
    # 步骤6b：清理以转义文本形式嵌入正文的广告 JS（实测 tid=159647 vbox 注入）
    s = VBOX_JS.sub("", s)
    # 步骤7：清理 onload 残留脚本碎片（实测存在 '700')this.width='700';... 泄漏）
    s = ONLOAD_FRAGMENT.sub("", s)
    s = ENLARGE_TAIL.sub("", s)
    # 步骤8：空白归一化
    s = SPACES.sub(" ", s)
    s = NEWLINES.sub("\n\n", s)
    return s.strip()


def assert_clean(s: str) -> list[str]:
    """质检：返回违反验收标准的关键词列表（空 = 通过）。"""
    violations: list[str] = []
    if "<" in s or ">" in s:
        violations.append("angle_brackets")
    if "this.width" in s or "this.height" in s:
        violations.append("onload_fragment")
    if "display:none" in s:
        violations.append("hidden_span")
    if "javascript" in s.lower():
        violations.append("js_fragment")
    if "Click Here To EnLarge" in s:
        violations.append("enlarge_tail")
    return violations
