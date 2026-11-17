"""HTTP 层测试：令牌桶间隔、GB18030 解码、无效 tid 判定。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.http import (  # noqa: E402
    TokenBucket,
    decode_gb18030,
    extract_title,
    is_valid_thread,
)


def test_token_bucket_min_interval() -> None:
    waits: list[float] = []
    bucket = TokenBucket(min_interval=2.0, jitter_ratio=0.0)
    bucket.acquire(sleeper=waits.append)   # 首次：不等待、不调用 sleeper
    bucket.acquire(sleeper=waits.append)   # 立即第二次 → 应等待 ≈2.0s
    bucket.acquire(sleeper=waits.append)
    assert len(waits) == 2, f"首次不应等待: {waits}"
    assert waits[0] >= 1.999, f"第二次等待 {waits[0]}"
    assert waits[1] >= 1.999, f"第三次等待 {waits[1]}"


def test_token_bucket_elapsed_time() -> None:
    import time as _t

    bucket = TokenBucket(min_interval=2.05, jitter_ratio=0.0)
    bucket.acquire()
    t0 = _t.monotonic()
    bucket.acquire()
    assert _t.monotonic() - t0 >= 2.0


def test_gb18030_decode() -> None:
    raw = "<title>贵州行＞刘玉石夫妻墓|≌≌阴宅风水≌≌</title>".encode("gb18030")
    text = decode_gb18030(raw)
    assert "刘玉石夫妻墓" in text
    assert extract_title(text).startswith("贵州行")


def test_utf8_page_detected() -> None:
    raw = '<html><meta charset="utf-8"><title>ok</title></html>'.encode("utf-8")
    assert decode_gb18030(raw) .find("ok") > 0


def test_is_valid_thread() -> None:
    ok = "<title>某帖|≌≌阴宅风水≌≌</title><div class='tpc_content'>正文</div>"
    bad_id = "<title>帖子ID非法 - 龙行天下风水论坛</title><div class='tpc_content'>x</div>"
    no_perm = "<title>某某</title>没有权限查看"
    empty = "<title>首页</title><div>nothing</div>"
    assert is_valid_thread(ok) is True
    assert is_valid_thread(bad_id) is False
    assert is_valid_thread(no_perm) is False
    assert is_valid_thread(empty) is False


def test_invalid_thread_from_real_site() -> None:
    """真实站点的无效 tid 页面特征（HTTP 200 + 标题判定）。"""
    body = (
        "<html><head><title>帖子ID非法 - 龙行天下风水论坛</title></head>"
        "<body>您所访问的帖子不存在或已被删除</body></html>"
    ).encode("gb18030")
    assert is_valid_thread(decode_gb18030(body)) is False


# ---------- 图片并发抓取（§2.1 并发 ≤3） ----------

def _tiny_png() -> bytes:
    """_fetch_row 会真解码校验，占位字节 b'ok' 过不了。"""
    import cv2
    import numpy as np
    return cv2.imencode('.png', np.zeros((4, 4, 3), np.uint8))[1].tobytes()


def test_iter_fetched_concurrent_covers_all_rows_in_order() -> None:
    """并发预取不能漏行、不能重复，序号要与行一一对应。"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.pipeline import _iter_fetched

    rows = [{"full_url": f"u{i}", "thumb_url": ""} for i in range(25)]
    img = _tiny_png()

    def fake_fetch(url: str):
        return img, False

    out = list(_iter_fetched(rows, fake_fetch, conc=3))
    assert len(out) == 25
    assert sorted(k for k, *_ in out) == list(range(25))
    assert {r["full_url"] for _, r, *_ in out} == {r["full_url"] for r in rows}
    assert all(data is not None for _, _, data, _, _ in out)


def test_iter_fetched_falls_back_to_thumb() -> None:
    """full 拿不到时回落 thumb，并记录实际使用的 url。"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.pipeline import _iter_fetched

    rows = [{"full_url": "full", "thumb_url": "thumb"}]
    img = _tiny_png()

    def fake_fetch(url: str):
        return (img, False) if url == "thumb" else (None, False)

    out = list(_iter_fetched(rows, fake_fetch, conc=2))
    assert out[0][2] == img and out[0][3] == "thumb"


def test_iter_fetched_rejects_truncated_full_and_uses_thumb() -> None:
    """站点断流会给出 200 + 半张图：必须判坏并回落 thumb，不能记成 DONE。"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.pipeline import _iter_fetched

    rows = [{"full_url": "full", "thumb_url": "thumb"}]
    img = _tiny_png()

    def fake_fetch(url: str):
        return (b"\xff\xd8\xff\xe0truncated", False) if url == "full" else (img, False)

    out = list(_iter_fetched(rows, fake_fetch, conc=1))
    assert out[0][2] == img and out[0][3] == "thumb"
