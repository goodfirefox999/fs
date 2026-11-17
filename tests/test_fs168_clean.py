"""fs168 Discuz 清洗器验收：引用标记、游客提示块删除、附件图占位、表情删除。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.fs168_clean import assert_clean, clean_post_html  # noqa: E402


def test_full_post_cleaning() -> None:
    raw = (
        '<td class="t_f" id="postmessage_1053079">'
        '<div class="attach_nopermission attach_tips"><div><h3><strong>'
        "马上注册，结交更多好友"
        "</strong></h3><p>您需要 <a href=\"member.php\">登录</a> 才可以下载</p></div></div>"
        "看此例：穴星端正，青龙白虎护卫。"
        '<div class="quote"><blockquote><font color="blue">原文：此局坐卯向酉</font></blockquote></div>'
        '<img id="aimg_SJ3iP" class="guestviewthumb_cur" onclick="showWindow(\'login\')" '
        'src="https://www.fengshui-168.com/fs168/discuz/discuzx/data/attachment/forum/201212/12/'
        '2335184h4h5smr4hzzrf42.jpg" border="0" alt="" />'
        '<img src="images/smilies/default/smile.gif" alt="" />'
        "图中可见来龙跌断再起。"
    )
    text, images = clean_post_html(raw)
    assert "马上注册" not in text                    # 游客提示块删除
    assert "登录" not in text
    assert "【引用】" in text and "此局坐卯向酉" in text   # 引用块保留并打标
    assert "[[IMG:1:2335184h4h5smr4hzzrf42]]" in text     # 附件图占位
    assert len(images) == 1                               # 表情图不登记
    assert "smilies" not in text
    assert "穴星端正" in text and "来龙跌断再起" in text
    assert assert_clean(text) == []


def test_nested_table_not_truncated() -> None:
    """正文里嵌表格（古籍帖常见）时，配对 </td> 不得提前截断。"""
    raw = (
        '前表如下：<table cellspacing="0"><tr><td>甲</td><td>子</td></tr></table>'
        "后文还有结论：此局大吉。"
    )
    text, images = clean_post_html(raw)
    assert "前表如下" in text
    assert "甲" in text and "子" in text
    assert "此局大吉" in text                              # 表格之后的内容未丢
    assert images == []


def test_guest_login_link_removed() -> None:
    raw = ('<img src="https://x.com/data/attachment/forum/201212/12/abc.jpg" />'
           '<a href="member.php?mod=logging&action=login" onclick="x()">登录/注册后可看大图</a>'
           "后续正文")
    text, images = clean_post_html(raw)
    assert "登录/注册后可看大图" not in text
    assert "[[IMG:1:abc]]" in text
    assert "后续正文" in text
