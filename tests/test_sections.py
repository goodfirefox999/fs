"""T6 分块与 v2 列表行解析测试（离线，不发网络请求）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.discover import parse_listing_rows  # noqa: E402
from src.extract_sections import analyze_sections, split_numbered_items  # noqa: E402

SAMPLE_POST = """【前言】应易友之邀，前往考察。
《人物简介》刘玉石，清代人氏。
【数据】
碑坐寅山66度
星顶：艮52度
朝山：申246度
倒戈山酉275度
内水口出：酉266度
【浅析】
1，来龙起伏有力，束气明白。
2，明堂团聚，水口紧锁。
3，穴星端正，土色润泽。
【历史查证】
1，十代内无中富中贵，平凡人家。
2，第十一代出陆军中将刘伯龙，1949年被枪杀。
3，当代族人无知名人才，以务农为主。
【后语】数据为罗盘实测，供研究。
"""


def test_split_sections() -> None:
    result = analyze_sections(SAMPLE_POST)
    assert set(result.sections) >= {"前言", "人物简介", "数据", "浅析", "历史查证", "后语"}
    assert result.has_structured_template is True
    assert result.template_richness >= 5
    assert "碑坐寅山66度" in result.sections["数据"]


def test_data_lines_feed_bearing() -> None:
    from src.extract_bearing import extract_bearings

    result = analyze_sections(SAMPLE_POST)
    obs = extract_bearings("\n".join(result.data_lines))
    labels = {o.label: o for o in obs}
    assert "碑坐" in labels and labels["碑坐"].shan24 == "寅"
    assert labels["碑坐"].category == "坐向"
    assert "倒戈山" in labels and labels["倒戈山"].degree == 275.0
    consistent = [o for o in obs if o.is_consistent]
    assert len(consistent) >= 4


def test_numbered_items() -> None:
    items = split_numbered_items("1，甲句。\n2，乙句。\n3，丙句。")
    assert len(items) == 3
    assert items[0] == "甲句。"


def test_history_generation_outcome() -> None:
    result = analyze_sections(SAMPLE_POST)
    gens = [h.generation_ref for h in result.history_items]
    # 文档样例：两种世代表述都应捕获
    assert "十代内" in gens
    assert "第十一代" in gens
    outcomes = [k for h in result.history_items for k in h.outcome_keywords]
    assert "中将" in outcomes
    assert "被枪杀" in outcomes
    assert "无知名" in outcomes or "知名人才" in outcomes


def test_no_template() -> None:
    result = analyze_sections("随便一段没有小标题的文字。")
    assert result.has_structured_template is False
    assert result.template_richness == 0


def test_listing_rows_parse() -> None:
    """v2 §1.2(2) 列表行结构：tid/标题/精华/含图/页数/作者/回复浏览/最后回复。"""
    row = (
        '<tr align="center" class="tr3 t_one">'
        '<td><a title="打开新窗口" href="read.php?tid=160140" target="_blank">'
        '<img src="images/wind/thread/topichot.gif" border=0 align="absmiddle"></a></td>'
        '<td style="text-align:left;" id="td_160140">'
        '<img src="images/wind/file/headtopic_3.gif" title="置顶帖标志"/>'
        '<h3><a href="read.php?tid=160140" id="a_ajax_160140"><b>某考察帖标题</b></a></h3>'
        "<span class='gray tpage'>( +1 )</span>"
        '<img src="images/wind/file/img.gif" border=0 align="absmiddle">'
        '<img src="images/wind/file/multipage.gif" border=0 align="absmiddle">'
        '<span style="font-family:verdana;">'
        '<a href="read.php?tid=160140&fpage=1&page=1">1</a>'
        '<a href="read.php?tid=160140&fpage=1&page=7">7</a></span></td>'
        '<td class="tal y-style"><a href="u.php?action=show&uid=1" class="bl">灵珠子</a>'
        '<div class="f10 gray2">2025-01-02</div></td>'
        '<td class="tal y-style f10"><span class="s8">62</span> / 49869</td>'
        '<td class="tal y-style"><a href="read.php?tid=160140&page=e&fpage=1#a"> '
        '2026-10-28 20:19 </a><br/><span class="gray2">by: yandianqi1</span></td></tr>'
    )
    rows = parse_listing_rows(row, fid=58)
    assert len(rows) == 1
    r = rows[0]
    assert r.tid == 160140 and r.fid == 58
    assert r.subject == "某考察帖标题"
    assert r.is_pinned is True
    assert r.has_image is True
    assert r.topic_pages == 7
    assert r.author_uid == 1 and r.author_name == "灵珠子"
    assert r.post_date == "2025-01-02"
    assert r.reply_count == 62 and r.view_count == 49869
    assert r.last_reply_time == "2026-10-28 20:19"
    assert r.last_replier == "yandianqi1"
    # 非精华
    assert r.is_digest is False
    # 普通行（无置顶、无图、单页、含精华标）
    row2 = (
        '<tr class="tr3 t_one"><td><a href="read.php?tid=4961">'
        '<img src="images/wind/thread/topicnew.gif"></a></td>'
        '<td id="td_4961">'
        '<img class="fr" src="images/wind/file/digest_2.gif" title="精华帖标志" />'
        '<h3><a href="read.php?tid=4961" id="a_ajax_4961">天然美穴你来点</a></h3></td>'
        '<td class="tal y-style"><a href="u.php?action=show&uid=6104" class="bl">天地缘</a>'
        '<div class="f10 gray2">2009-07-20</div></td>'
        '<td class="tal y-style f10"><span class="s8">640</span> / 475441</td></tr>'
    )
    rows2 = parse_listing_rows(row2, fid=58)
    r2 = rows2[0]
    assert r2.tid == 4961 and r2.is_digest is True and r2.is_pinned is False
    assert r2.has_image is False and r2.topic_pages == 1
    assert r2.author_uid == 6104 and r2.reply_count == 640


def test_text_before_first_anchor_preserved() -> None:
    """v3 N-10 修复：首锚点之前的正文保留为「开篇」，且不计入丰富度。"""
    text = "本帖是楼主实地考察的手记。\n【数据】\n碑坐寅山66度\n"
    result = analyze_sections(text)
    assert "开篇" in result.sections
    assert "实地考察的手记" in result.sections["开篇"]
    assert result.sections["数据"].strip() == "碑坐寅山66度"
    # 开篇不是锚点：不得把「有开头正文 + 少量锚点」误判为结构化帖
    assert result.template_richness == 1
    assert result.has_structured_template is False


def test_duplicate_anchor_appends_not_overwrites() -> None:
    """v3 N-10 修复：同名锚点追加而非覆盖，两段数据行都参与罗盘抽取。"""
    text = "【数据】\n甲山100度\n【浅析】\n1，前段。\n【数据】\n乙山200度\n"
    result = analyze_sections(text)
    assert "甲山100度" in result.sections["数据"]
    assert "乙山200度" in result.sections["数据"]
    assert result.data_lines == ["甲山100度", "乙山200度"]
    assert result.template_richness == 2
