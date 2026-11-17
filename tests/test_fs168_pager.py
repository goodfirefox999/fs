"""fs168 分页器页数识别（离线回归测试）。

背景（2026-11-02）：原实现只允许 `class="pg"` 后 900 字符内出现
`<span title="共 N 页"`。Discuz 的大帖分页器会先铺 10 个页码链接，
页数越多 span 越靠后，超过 900 就判成 1 页 → 只抓 p1，整帖只剩前 30 层。
实测 56 帖（回复数百的高价值案例帖）因此漏采 926 页。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scrapers'))

from fs168_threads import parse_thread_page  # noqa: E402


def _pager(tid: int, total: int, compact: bool = True) -> str:
    """复刻 Discuz X3 的 pgs 容器：10 个页码链接 + 页数标记。

    compact=True 用真实形态 `<span title="共 N 页"> / N 页</span>`
    （12995 等大帖即此形态，span 距容器起点 ~1000 字符）。
    """
    links = ''.join(
        f'<a href="https://www.fengshui-168.com/thread-{tid}-{p}-1.html">{p}</a>'
        for p in range(2, 11)
    )
    tail = (f'<a href="https://www.fengshui-168.com/thread-{tid}-{total}-1.html" '
            f'class="last">{total} / {total} 页</a>')
    span = (f'<span title="共 {total} 页"> / {total} 页</span>')
    return (f'<div id="pgt" class="pgs mbm cl "><div class="pgt"><div class="pg">'
            f'<strong>1</strong>{links}{tail}{span}</div></div></div>')


FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'tid12995_pager.html'


def test_large_pager_is_not_misread_as_single_page():
    """真实片段：tid=12995，共 37 页，页数 span 距 pgs 容器起点约 1000 字符。"""
    html = FIXTURE.read_text(encoding='utf-8')
    assert len(html) > 900, '该夹具必须超过旧的 900 字符窗口，否则测不到回归'
    assert parse_thread_page(html)['total_pages'] == 37


def test_small_pager_still_works():
    html = _pager(55039, 6)
    assert parse_thread_page(html)['total_pages'] == 6


def test_no_pager_defaults_to_one_page():
    # 71155：游客只能看到 1 层，页面根本没有分页器（权限/隐藏帖）
    html = '<div id="post_1">正文</div>'
    assert parse_thread_page(html)['total_pages'] == 1


def test_sidebar_title_with_page_count_is_not_a_pager():
    """侧栏「相关帖子」标题里带「共76页」，不得被当成总页数。

    tid=253072 实证：裸正则 `共 N 页` 会把它读成 76 页，触发 75 页无效抓取。
    """
    html = (
        '<div id="post_1">正文</div>'
        '<li><a title="刘伯温先生龙穴砂水诀（道法双谭共76页">刘伯温先生龙穴砂水诀</a></li>'
    )
    assert parse_thread_page(html)['total_pages'] == 1


@pytest.mark.parametrize('total', [1, 2, 11, 37, 60])
def test_pager_roundtrip(total: int):
    html = _pager(999, total) if total > 1 else '<div id="post_1"></div>'
    assert parse_thread_page(html)['total_pages'] == total
