"""帖子页解析（文档 T3）：楼层、作者块、评分记录、att 图片、分页。

结构锚点全部来自实测（tid=163913，2026-10-26）：
  楼层正文  <div class="f14" id="read_tpc"> / <div class="f14" id="read_{pid}">
            （旧模板为 class="tpc_content"，同 id，一并兼容）
  楼层时间  <span class="fl gray" title="2026-10-26 20:43" style="...">发表于: ...</span>
  作者块    <a href="u.php?action=show&uid=1" target="_blank">灵珠子</a>
            随后 UID/精华/发帖/威望/金钱/贡献值/好评度/在线时间/注册时间/最后登录
  评分记录  <li>金钱:+200(2010龙坛学习) 优秀文章</li>
  引用链接  post.php?action=quote&fid=58&tid=...&pid={pid}&article={楼层序号}
  att 图片  <span id="att_{aid}">…thumb src + onclick full + <b>图前注</b>…</span>
"""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field

from .images import ImageRef, extract_att_images

FLOOR_OPEN = re.compile(r'<div[^>]*class="(?:f14|tpc_content)[^"]*"\s+id="(read_tpc|read_\d+)"[^>]*>')
AUTHOR_RE = re.compile(r'u\.php\?action=show&(?:amp;)?uid=(\d+)"[^>]*>([^<]{1,30})</a>')
TIME_RE = re.compile(r'<span class="fl gray" title="(\d{4}-\d{2}-\d{2} \d{2}:\d{2})"[^>]*>')
# 老导入帖的畸形楼层头：相对日期（昨天/今天）、无 fl gray/title、楼号彩字
# （实测 tid=24433 楼 366182）。与 TIME_RE 互斥，二者并集才是完整楼层头集合。
HEADER_BARE_RE = re.compile(r'<span style="color:#ff6600 ">\d{1,4}楼</span>\s*(?:&nbsp;)?\s*发表于:')
# phpwind 楼层表格行（tr1/tr2 交替底色）。作者资料块位于下一楼行首之后、时间头之前，
# 失配 div 会把它一并吞进上一楼正文——用行首作最后一段边界。
FLOOR_ROW = re.compile(r'<tr class="tr[12]"')
# 老导入帖（实测 tid=24433/56330）作者块在正文之后：签名=「u.php 头像链接」（链接内直接嵌 img，
# 正文里的用户链接是文字子节点，不会误伤）；页脚管理栏签名=masingle.php 管理链接。
# 注：作者名文本可留在正文尾（诚实且无害）；不向回吞字符，避免在标签内制造切点。
AUTHOR_BLOCK = re.compile(r'<a href="[^"]*u\.php\?action=show&(?:amp;)?uid=\d+"[^>]*>\s*<img\b', re.I)
# 无头像变体（实测 13 层）：「级别: X」后 200 字内必跟「作者资料」菜单，以此锚定块头
AUTHOR_BLOCK_TXT = re.compile(r'级别\s*[:：][\s\S]{0,200}?作者资料', re.I)
FOOTER_PING = re.compile(r'<a href="[^"]*masingle\.php\?action=(?:pingcp|banuser|shield|remind)', re.I)
SCORE_RE = re.compile(r"<li>\s*(金钱|威望|贡献值|好评度)\s*:\s*\+?(-?\d+)\(([^)]+)\)\s*([^<]*?)\s*</li>")
QUOTE_RE = re.compile(r"post\.php\?action=quote&(?:amp;)?fid=(\d+)&(?:amp;)?tid=(\d+)&(?:amp;)?pid=(\w+)&(?:amp;)?article=(\d+)")
PAGE_LINK_RE = re.compile(r'read\.php\?tid=(\d+)&(?:amp;)?[^"\']*page=(\d+)')
# 页脚边界：phpwind 每楼层正文之后、签名/评分/操作栏之前必有 sigline div（实测 2010~2026 各年代页均存在）。
# 楼层内容 div 偶有未闭合（如老帖引用块），配对闭合会吞掉后续楼层——用 sigline 兜底截断。
SIGLINE = re.compile(r'<div class="sigline"', re.I)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
SUBJECT_RE = re.compile(r'id="subject_tpc"[^>]*>([\s\S]{0,200}?)</')
UID_META_RE = re.compile(r"UID\s*[:：]\s*<span[^>]*>(\d+)</span>")
META_KEYS = ["精华", "发帖", "威望", "金钱", "贡献值", "好评度", "在线时间", "注册时间", "最后登录"]


@dataclass
class PeerScore:
    score_type: str
    value: int
    rater: str
    reason: str


@dataclass
class FloorParse:
    pid: str                    # 楼主层为 'tpc'
    floor_index: int
    author_uid: int | None
    author_name: str | None
    author_meta: dict[str, str] = field(default_factory=dict)
    post_time: str | None = None
    subject: str | None = None
    is_op: bool = False
    content_span: tuple[int, int] = (0, 0)   # 内容 div 在页 HTML 中的区间
    raw_html: str = ""
    scores: list[PeerScore] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)


@dataclass
class PageParse:
    tid: int
    title: str
    forum_name: str | None
    fid: int | None
    page: int
    page_count: int
    paywalled: bool
    floors: list[FloorParse]


def extract_title(html_text: str) -> tuple[str, str | None]:
    """返回 (帖子标题, 版块名)。"""
    m = TITLE_RE.search(html_text)
    if not m:
        return "", None
    parts = m.group(1).strip().split("|")
    forum_name: str | None = None
    if len(parts) > 1:
        seg = parts[1].split("-")[0]
        name = seg.strip().strip("≌ ").strip()
        forum_name = name or None
    return parts[0].strip(), forum_name


def parse_fid(html_text: str) -> int | None:
    m = QUOTE_RE.search(html_text)
    return int(m.group(1)) if m else None


def parse_page_count(html_text: str, tid: int) -> int:
    n = 1
    for m in PAGE_LINK_RE.finditer(html_text):
        if int(m.group(1)) == tid:
            n = max(n, int(m.group(2)))
    return min(n, 1000)


def is_paywalled(html_text: str) -> bool:
    return "buytopic" in html_text or "金钱购买" in html_text or "需要支付" in html_text


def extract_author_meta(slice_html: str) -> dict[str, str]:
    """从作者块切片提取统计字段（best-effort，缺失即缺）。"""
    meta: dict[str, str] = {}
    for key in META_KEYS:
        m = re.search(
            key + r"\s*[:：]\s*(?:<a[^>]*>)?(?:<span[^>]*>)?([^<\r\n]{1,40}?)"
            r"(?:</span>|</a>)?\s*(?:<br)",
            slice_html,
        )
        if m:
            meta[key] = m.group(1).strip().rstrip("点(时)RMB ").strip()
    m_uid = UID_META_RE.search(slice_html)
    if m_uid:
        meta["UID"] = m_uid.group(1)
    return meta


def _balanced_div_end(html_text: str, open_end: int) -> int:
    """返回与楼层内容 div 配对的 </div> 之后的位置。"""
    depth = 1
    i = open_end
    tag = re.compile(r"<div\b|</div", re.I)
    while i < len(html_text) and depth > 0:
        m = tag.search(html_text, i)
        if not m:
            return len(html_text)
        if m.group(0).lower() == "<div":
            depth += 1
        else:
            depth -= 1
        i = m.end()
    close = html_text.find(">", i - 1)
    return close + 1 if close >= 0 else i


def parse_floors(page_html: str) -> list[FloorParse]:
    """按楼层 div 顺序切分并归属作者/时间/评分/图片。"""
    opens = list(FLOOR_OPEN.finditer(page_html))
    floors: list[FloorParse] = []
    # 引用链接表：pid -> article（楼层序号）
    article_map = {m.group(3): int(m.group(4)) for m in QUOTE_RE.finditer(page_html)}
    fid = parse_fid(page_html)

    author_hits = [(m.start(), int(m.group(1)), m.group(2)) for m in AUTHOR_RE.finditer(page_html)]
    time_hits = sorted(
        [(m.start(), m.group(1)) for m in TIME_RE.finditer(page_html)]
        + [(m.start(), None) for m in HEADER_BARE_RE.finditer(page_html)]
    )
    time_positions = [pos for pos, _ in time_hits]

    prev_content_end = 0
    for k, m in enumerate(opens):
        pid = m.group(1)[5:] if m.group(1) != "read_tpc" else "tpc"
        cs = m.end()
        ce = opens[k + 1].start() if k + 1 < len(opens) else len(page_html)
        content_end = min(_balanced_div_end(page_html, cs), ce)
        sig = SIGLINE.search(page_html, cs, ce)
        if sig:
            content_end = min(content_end, sig.start())
        # 下一楼「发表于」头是硬边界：正文绝不越过它（老导入帖实测 tid=24433，
        # 引用块 div 失配时配对闭合会吞掉下一楼整块；畸形头由 HEADER_BARE_RE 兜住）
        nt = bisect_right(time_positions, cs)
        if nt < len(time_positions):
            content_end = min(content_end, time_positions[nt])
        # 下一楼表格行首更靠前（作者资料块在时间头之前），一并截住
        row = FLOOR_ROW.search(page_html, cs, ce)
        if row:
            content_end = min(content_end, row.start())
        # 老导入帖：作者块/页脚管理栏在正文之后，失配 div 会吞进来——按签名截断
        for pat in (AUTHOR_BLOCK, AUTHOR_BLOCK_TXT, FOOTER_PING):
            mm = pat.search(page_html, cs, content_end)
            if mm:
                content_end = min(content_end, mm.start())
        raw = page_html[cs:content_end]
        # 边界可能落在标签中间，截去尾部不完整的 '<...'（否则 ANY_TAG 剥不掉）
        lt, gt = raw.rfind("<"), raw.rfind(">")
        if lt > gt:
            raw = raw[:lt]

        # 作者/时间：取内容 div 之前最近的未消费块
        prev_end = opens[k - 1].end() if k > 0 else 0
        uid = name = None
        for pos, u, n in reversed(author_hits):
            if prev_end <= pos < cs and n not in ("作者资料", "发短消息", "加为好友", "QQ联系"):
                uid, name = u, n
                break
        ptime: str | None = None
        for pos, t in reversed(time_hits):
            if prev_end <= pos < cs:
                ptime = t
                break
        meta = extract_author_meta(page_html[max(prev_end, cs - 6000) : cs])

        # 评分记录：本层内容与下一层内容之间的 <li>
        scores = [
            PeerScore(g.group(1), int(g.group(2)), g.group(3), g.group(4))
            for g in SCORE_RE.finditer(page_html, cs, ce)
        ]

        fp = FloorParse(
            pid=pid,
            floor_index=article_map.get(pid, k),
            author_uid=uid,
            author_name=name,
            author_meta=meta,
            post_time=ptime,
            is_op=(pid == "tpc"),
            content_span=(cs, ce),
            raw_html=raw,
            scores=scores,
        )
        fp.images = extract_att_images(
            page_html, tid=0, pid=pid, fid=fid or 0, author_uid=uid or 0,
            content_start=cs, content_end=content_end,
            # 老模板附件容器在正文 div 之前，扫描区往前扩到上一层正文结束处
            scan_start=prev_content_end,
        )
        floors.append(fp)
        prev_content_end = content_end

    # 兜底：老导入帖个别楼层丢失内容 div（实测 tid=24433 楼 366182：正文是 <td> 裸文本，
    # 无 read_ 容器，FLOOR_OPEN 匹配不到，且会被上一楼失配 div 吞并）。
    # 若某「发表于」头到下一头之间没有任何楼层，依据区间内 quote 锚反推 pid，
    # 正文取头部标记之后、评分块/页脚/<tr> 边界之前，抢救为独立楼层。
    BARE_HEADER_TAIL = re.compile(r"小\s*中\s*大")
    BARE_CUT = re.compile(r"本帖最近评分记录|<tr\b|post\.php\?action=quote", re.I)
    bare: list[FloorParse] = []
    for i, (tpos, tval) in enumerate(time_hits):
        nxt = time_positions[i + 1] if i + 1 < len(time_positions) else len(page_html)
        if any(tpos <= f.content_span[0] < nxt for f in floors):
            continue
        region_start = time_positions[i - 1] if i else 0
        uid = name = None
        for pos, u, n in reversed(author_hits):
            if region_start <= pos < tpos and n not in ("作者资料", "发短消息", "加为好友", "QQ联系"):
                uid, name = u, n
                break
        m_head = BARE_HEADER_TAIL.search(page_html, tpos, nxt)
        cs2 = m_head.end() if m_head else tpos
        m_cut = BARE_CUT.search(page_html, cs2, nxt)
        ce2 = m_cut.start() if m_cut else nxt
        qm = QUOTE_RE.search(page_html, tpos, nxt)
        pid = qm.group(3) if qm else f"bare{i}"
        fp = FloorParse(
            pid=pid,
            floor_index=article_map.get(pid, 10 ** 6 + i),
            author_uid=uid,
            author_name=name,
            post_time=tval,
            is_op=False,
            content_span=(cs2, ce2),
            raw_html=page_html[cs2:ce2],
        )
        fp.images = extract_att_images(
            page_html, tid=0, pid=pid, fid=fid or 0, author_uid=uid or 0,
            content_start=cs2, content_end=ce2, scan_start=region_start,
        )
        bare.append(fp)
    floors.extend(bare)

    # 楼层序号兜底：article_map 缺失时按出现顺序
    for k, fp in enumerate(floors):
        if fp.pid != "tpc" and fp.floor_index == 0:
            fp.floor_index = k
    floors.sort(key=lambda f: f.floor_index)
    return floors


def parse_page(page_html: str, tid: int, page: int) -> PageParse:
    title, forum_name = extract_title(page_html)
    floors = parse_floors(page_html)
    # 标题里可能带楼层锚点噪音，截断
    title = re.sub(r"\s*- 龙行天下.*$", "", title).strip()
    subject_m = SUBJECT_RE.search(page_html)
    subject = re.sub(r"<[^>]+>", "", subject_m.group(1)).strip() if subject_m else None
    if floors and floors[0].is_op:
        floors[0].subject = subject
    return PageParse(
        tid=tid,
        title=title,
        forum_name=forum_name,
        fid=parse_fid(page_html),
        page=page,
        page_count=parse_page_count(page_html, tid),
        paywalled=is_paywalled(page_html),
        floors=floors,
    )
