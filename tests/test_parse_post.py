"""T3/T4 解析与清洗：tid=163913 归档 fixture 验收断言。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.clean import assert_clean, clean_floor_html  # noqa: E402
from src.images import ImageRegistry  # noqa: E402
from src.parse_post import parse_fid, parse_floors, parse_page, parse_page_count  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "tid163913_p1.html"


def load_fixture() -> str:
    return FIXTURE.read_bytes().decode("gb18030", errors="replace")


def test_decode_gb18030_title_readable() -> None:
    h = load_fixture()
    assert "刘玉石夫妻墓" in h or "刘伯龙" in h


def test_parse_title_forum_fid() -> None:
    h = load_fixture()
    from src.parse_post import extract_title

    title, forum = extract_title(h)
    assert "刘玉石夫妻墓" in title
    assert forum == "阴宅风水"
    assert parse_fid(h) == 58


def test_parse_page_count_single_page_ok() -> None:
    h = load_fixture()
    # fixture 是第 1 页；页数应为 >=1（该帖共 9 页，但 fixture 只含第 1 页链接）
    assert parse_page_count(h, 163913) >= 1


def test_floors_structure() -> None:
    pp = parse_page(load_fixture(), 163913, 1)
    assert pp.fid == 58
    assert len(pp.floors) >= 10
    op = pp.floors[0]
    assert op.is_op is True
    assert op.pid == "tpc"
    assert op.author_uid == 1
    assert op.author_name == "灵珠子"
    assert op.post_time == "2026-10-26 20:43"
    assert op.subject and "刘玉石夫妻墓" in op.subject
    # 评分记录
    all_scores = [s for f in pp.floors for s in f.scores]
    assert len(all_scores) >= 8
    assert any(s.reason == "判断准确" and s.rater == "巫鸿山" and s.score_type == "威望" for s in all_scores)
    # 图片
    n_imgs = sum(len(f.images) for f in pp.floors)
    assert n_imgs == 17, f"期望 17 图，得到 {n_imgs}"
    first_img = [i for f in pp.floors for i in f.images][0]
    assert first_img.thumb_url and "/thumb/" in first_img.thumb_url
    assert first_img.full_url and "/thumb/" not in first_img.full_url
    assert "Mon_2610/58_1_61e1c1ae4b410cf" in first_img.full_url
    assert first_img.caption_before == "01，无人机看来龙"


def test_clean_no_js_and_img_placeholders() -> None:
    h = load_fixture()
    pp = parse_page(h, 163913, 1)
    all_refs = [i for f in pp.floors for i in f.images]
    registry = ImageRegistry(tid=163913, pid="tpc", fid=58, author_uid=1, refs=list(all_refs))
    cleaned = clean_floor_html("\n".join(f.raw_html for f in pp.floors), registry)
    violations = assert_clean(cleaned)
    assert violations == [], f"清洗残留: {violations}"
    assert "<" not in cleaned and ">" not in cleaned
    assert "this.width" not in cleaned
    assert "display:none" not in cleaned
    n_ph = cleaned.count("[[IMG:")
    assert n_ph == 17, f"占位符应为 17，得到 {n_ph}"
    assert first_img_caption_ok(pp)
    assert "[图:" not in cleaned


def first_img_caption_ok(pp: object) -> bool:
    from src.parse_post import PageParse  # 局部导入避免循环
    assert isinstance(pp, PageParse)
    imgs = [i for f in pp.floors for i in f.images]
    return imgs and imgs[0].caption_before == "01，无人机看来龙"


def test_clean_disabled_hidden_span() -> None:
    """反爬 span 必须在抽文本前删除（顺序1）。"""
    raw = '<div>正文一<span style="display:none"> Xk#(psU </span>正文二<img src="http://x/attachment/Mon_2610/58_1_hash.jpg"></div>'
    reg = ImageRegistry(tid=1, pid="tpc", fid=58, author_uid=1, refs=[])
    out = clean_floor_html(raw, reg)
    assert "Xk#(psU" not in out
    assert "正文一" in out and "正文二" in out
    assert "[[IMG:1:58_1_hash]]" in out
