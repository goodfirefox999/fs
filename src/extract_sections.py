"""结构化小标题分块（文档 T6）。

锚点体裁：【前言】【数据】【浅析】【历史查证】【评分记录】【后语】等。
【数据】逐行交给 T5；【浅析】【历史查证】拆条目并抽世代/结果关键词。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTION_ANCHORS: list[str] = [
    "【前言】", "《人物简介》", "【数据】", "【浅析】", "【历史查证】",
    "【评分记录】", "【后语】", "【结语】", "【勘察背景】", "【调整方案】", "【实证效果】",
]

GEN_PAT = re.compile(r"第?[一二三四五六七八九十百千0-9０-９]{1,7}代(?:内|之内|以前)?|十代内|[一二三四五六七八九十]{1,3}代内")
OUTCOME_TERMS = [
    "中将", "少将", "上将", "将军", "司令", "进士", "举人", "状元", "尚书", "巡抚",
    "总督", "知府", "县长", "市长", "省长", "厅级", "处级", "教授", "主任医师",
    "博士", "硕士", "大学生", "老板", "富豪", "千万", "亿万", "富裕", "小康",
    "被枪杀", "枪杀", "被害", "夭折", "无后", "绝嗣", "早逝", "离婚", "坐牢",
    "知名人才", "无知名", "无出", "无中", "出中", "富", "贵", "贫困", "平凡",
]
NUMBERED = re.compile(r"(?:^|\n)\s*(\d{1,2})\s*[，,、.．]\s*")


@dataclass
class Section:
    name: str
    content: str
    order: int
    items: list[str] = field(default_factory=list)


@dataclass
class HistoryItem:
    content: str
    generation_ref: str | None
    outcome_keywords: list[str]


@dataclass
class SectionResult:
    sections: dict[str, str]
    template_richness: int
    has_structured_template: bool
    data_lines: list[str]
    qianxi_items: list[str]
    history_items: list[HistoryItem]


def split_sections(text: str) -> list[Section]:
    """按锚点位置切分；锚点间文本归属前一个锚点。"""
    hits: list[tuple[int, str]] = []
    for anchor in SECTION_ANCHORS:
        start = 0
        while True:
            i = text.find(anchor, start)
            if i < 0:
                break
            hits.append((i, anchor))
            start = i + len(anchor)
    hits.sort()
    sections: list[Section] = []
    for k, (pos, name) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(text)
        body = text[pos + len(name) : end].strip()
        sections.append(Section(name=name.strip("【】《》"), content=body, order=k))
    return sections


def split_numbered_items(body: str) -> list[str]:
    """按 '1，' '2，' 序号拆条目（跨行条目合并）。"""
    marks = list(NUMBERED.finditer(body))
    if not marks:
        return [body.strip()] if body.strip() else []
    items: list[str] = []
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(body)
        item = body[m.end() : end].strip()
        if item:
            items.append(item)
    return items


def extract_history_item(content: str) -> HistoryItem:
    gen = GEN_PAT.search(content)
    outcomes = [t for t in OUTCOME_TERMS if t in content]
    return HistoryItem(
        content=content,
        generation_ref=gen.group(0) if gen else None,
        outcome_keywords=outcomes,
    )


def analyze_sections(uid1_text: str) -> SectionResult:
    sections = split_sections(uid1_text)
    names = [s.name for s in sections]
    richness = len(set(names))
    data_lines: list[str] = []
    qianxi_items: list[str] = []
    history_items: list[HistoryItem] = []
    for s in sections:
        if s.name == "数据":
            data_lines = [ln.strip() for ln in s.content.splitlines() if ln.strip()]
            s.items = data_lines
        elif s.name == "浅析":
            qianxi_items = split_numbered_items(s.content)
            s.items = qianxi_items
        elif s.name in ("历史查证", "历史勘验"):
            history_items = [extract_history_item(x) for x in split_numbered_items(s.content)]
            s.items = [h.content for h in history_items]
    return SectionResult(
        sections={s.name: s.content for s in sections},
        template_richness=richness,
        has_structured_template=richness >= 3,
        data_lines=data_lines,
        qianxi_items=qianxi_items,
        history_items=history_items,
    )
