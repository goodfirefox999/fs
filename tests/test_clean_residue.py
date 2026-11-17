"""2026-11-04 残留修复回归测试：
1. vbox 广告 JS（转义文本嵌入正文）必须被清洗掉（tid=159647 实测案例）
2. att_ span 里 zip/torrent 等 UI 图标不得登记为图片资产（tid=82276 实测案例）
3. 内容 div 未闭合时楼层边界必须被 sigline 截断，不得吞掉页脚/下一楼（tid=24433 实测案例）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.clean import assert_clean, clean_floor_html  # noqa: E402
from src.images import ImageRegistry, extract_att_images  # noqa: E402
from src.parse_post import parse_floors  # noqa: E402


def _registry() -> ImageRegistry:
    return ImageRegistry(tid=1, pid="tpc", fid=58, author_uid=1, refs=[])


def test_vbox_js_removed() -> None:
    raw = (
        '个人浅见，穴星来脉太急太冲。 <img src="http://x.com/images/post/smile/1.gif" /> '
        'if (typeof window.top.__vbox_invoke_ids === "undefined") {'
        'window.top.__vbox_invoke_ids = 100;window.top.__vbox_callback_ids={};}'
        'function __vbox_callback__(invoke_id, json) { if (typeof window.top'
        '.__vbox_callback_ids[invoke_id] === "function") { } })();'
        "(function() {\xa0\xa0\xa0\xa0setTimeout(function(){\xa0\xa0\xa0\xa0"
        'if (typeof vbox != "undefined") {\xa0\xa0\xa0\xa0'
        "var iframes = window.document.getElementsByTagName('iframe');\xa0\xa0\xa0\xa0"
        'for (var i = 0; i < iframes.length; ++i) {\xa0\xa0\xa0\xa0}'
        "\xa0\xa0\xa0\xa0}, 500);})();"
        "[ 此帖被某人在2024-12-29 15:30重新编辑 ]"
    )
    out = clean_floor_html(raw, _registry())
    assert "__vbox" not in out
    assert "invoke_ids" not in out
    assert "vbox" not in out                    # IIFE 包装段也必须整体移除
    assert "setTimeout" not in out
    # 表情图（非 attachment）应被丢弃，正文语义与编辑记录保留
    assert "穴星来脉太急太冲" in out
    assert "重新编辑" in out
    assert assert_clean(out) == []


def test_zip_icon_span_skipped() -> None:
    page = (
        '<div class="f14" id="read_tpc">正文'
        '<span id="att_263753"><img src="images/wind/file/zip.gif" align="absmiddle" />'
        '<a href="job.php?action=download&aid=263753">附件.zip</a></span>'
        "</div>"
    )
    refs = extract_att_images(page, tid=82276, pid="tpc", fid=9, author_uid=1,
                              content_start=0, content_end=len(page))
    assert refs == []


def test_floor_boundary_sigline() -> None:
    # 楼层1 内容 div 内部少一个 </div>（老帖引用块实测形态），
    # 配对闭合会一路吞到页尾——必须被 sigline 截断。
    page = (
        '<div class="f14" id="read_tpc">第一楼正文<div class="quote">引用'
        '<div class="sigline"></div>'
        '<div class="tips">7楼footer 顶端 回复 评分管理 禁言 [url=javascript:scroll(0,0)]顶端[/url]</div>'
        '<div class="f14" id="read_99">第二楼正文：此课用后140天长子死'
        '<div class="sigline"></div>'
        "<div>页尾残余</div>"
    )
    floors = parse_floors(page)
    assert [f.pid for f in floors] == ["tpc", "99"]
    f1 = floors[0]
    assert "第一楼正文" in f1.raw_html
    assert "引用" in f1.raw_html                    # 引用块本身属于本层，保留
    assert "顶端" not in f1.raw_html                 # 页脚操作栏不得混入
    assert "评分管理" not in f1.raw_html
    assert "第二楼正文" not in f1.raw_html           # 下一楼内容不得混入
    f2 = floors[1]
    assert "第二楼正文" in f2.raw_html
    assert "页尾残余" not in f2.raw_html             # sigline 截断页尾


def test_bare_floor_synthesis() -> None:
    """老导入帖：8 楼丢失内容 div（正文为 <td> 裸文本），必须被抢救为独立楼层，
    且不得被 7 楼失配的内容 div 吞并（实测 tid=24433 楼 366182）。"""
    page = (
        '<a href="u.php?action=show&uid=24">7楼作者</a>'
        '<span class="fl gray" title="2011-09-25 17:00">发表于: 2011-09-25 17:00</span>'
        '<div class="f14" id="read_367021">7楼回复<div class="quote">引用'
        '<div class="text">被引内容</div></blockquote>'
        # 8 楼：畸形头（相对日期、彩字楼号、无 fl gray），正文无 read_ 容器
        '<a href="u.php?action=show&uid=65052">某人</a>'
        '<span style="color:#ff6600 ">8楼</span>&nbsp; 发表于: 昨天 &nbsp;|&nbsp;'
        '<font size="6"><b></b></font><br />小 中 大 此课用后140天长子死次子破财。'
        '<tr class="tr5"><td>本帖最近评分记录：金钱:+120(自然风) 精彩回复'
        '<a href="post.php?action=quote&fid=5&tid=24378&pid=366182&article=8&page=1">引用</a>'
        '<div class="sigline"></div>'
        # 9 楼：正常
        '<a href="u.php?action=show&uid=99">9楼作者</a>'
        '<span class="fl gray" title="2011-09-25 19:00">发表于: 2011-09-25 19:00</span>'
        '<div class="f14" id="read_367201">9楼正文<div class="sigline"></div>'
    )
    floors = parse_floors(page)
    pids = [f.pid for f in floors]
    assert "366182" in pids, pids
    f8 = [f for f in floors if f.pid == "366182"][0]
    assert f8.floor_index == 8
    assert f8.author_uid == 65052
    assert "此课用后140天长子死次子破财" in f8.raw_html
    assert "本帖最近评分记录" not in f8.raw_html      # 评分块/页脚切干净
    assert "post.php" not in f8.raw_html
    assert "sigline" not in f8.raw_html
    f7 = [f for f in floors if f.pid == "367021"][0]
    assert "被引内容" in f7.raw_html                  # 本层引用块保留
    assert "此课用后" not in f7.raw_html              # 不吞下一楼裸文本
    assert "发表于" not in f7.raw_html                # 不吞下一楼时间头


def test_trailing_author_block_and_footer_trimmed() -> None:
    """老导入帖：作者块（头像链接+级别/UID 表）与评分管理页脚位于正文之后，
    失配 div 会吞进来，必须按签名截断（实测 tid=24433/56330）。"""
    page = (
        '<span class="fl gray" title="2011-09-25 17:00">发表于: 2011-09-25 17:00</span>'
        '<div class="f14" id="read_tpc">7楼正文，慢慢看吧<div class="quote">引用'
        '<div class="text">被引内容</div></blockquote>'
        '<tr class="tr5"><td colspan="1"><a href="http://x.com/u.php?action=show&amp;uid=65052" '
        'target="_blank"><img src="http://x.com/images/face/none.gif" /></a></td></tr></table>'
        '级别: 钻石会员<br />UID: 65052<br />精华: 0<br />发帖: 372<br />最后登录: 2011-09-25'
        '<tr class="tr5"><td><a href="http://x.com/masingle.php?action=pingcp&amp;fid=5">评分管理</a>'
        ' 共条评分 顶端 回复 引用 举报'
    )
    floors = parse_floors(page)
    assert len(floors) == 1
    raw = floors[0].raw_html
    assert "慢慢看吧" in raw
    assert "被引内容" in raw
    assert "级别" not in raw and "钻石会员" not in raw
    assert "发帖: 372" not in raw and "最后登录" not in raw
    assert "评分管理" not in raw and "共条评分" not in raw


def test_partial_tag_at_boundary_trimmed() -> None:
    """边界落在标签中间时，尾部半截 '<...' 必须被修剪，不得漏入正文
    （实测 367021 尾部曾出现字面 '<td cols'）。"""
    page = (
        '<span class="fl gray" title="2011-09-25 17:00">发表于: 2011-09-25 17:00</span>'
        '<div class="f14" id="read_tpc">正文，慢慢看吧</div>'
        '<td colspan="1" rowspan="1" width="1"><a href="u.php?action=show&amp;uid=65052">'
        '<img src="face.gif" /></a>级别: 钻石会员'
    )
    floors = parse_floors(page)
    raw = floors[0].raw_html
    assert "慢慢看吧" in raw
    assert "级别" not in raw
    assert raw.endswith("吧") or raw.endswith(">") or raw.endswith('"')


def test_author_block_text_variant_trimmed() -> None:
    """无头像变体的作者块（「级别:」+「作者资料/发送短消息/UID…」文字链）也要截掉
    （实测 13 层，如 3246_749534 灵珠子作者块）。"""
    page = (
        '<span class="fl gray" title="2011-09-25 17:00">发表于: 2011-09-25 17:00</span>'
        '<div class="f14" id="read_tpc">得运就能勃然而兴. 真理!!!!</div>'
        '灵珠子 \xa0\n万法皆由缘\xa0\n级别: 总坛主\xa0\n'
        '<a href="u.php?action=show&amp;uid=1">作者资料</a>'
        '<a href="u.php?action=write&amp;uid=1">发送短消息</a>'
        'UID: 1<br />精华: 12<br />发帖: 6325<br />最后登录: 2026-10-26'
    )
    floors = parse_floors(page)
    raw = floors[0].raw_html
    assert "勃然而兴" in raw
    assert "作者资料" not in raw and "发送短消息" not in raw
    assert "UID" not in raw and "精华" not in raw
    assert "级别" not in raw
