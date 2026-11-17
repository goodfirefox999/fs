"""discover_digest_all 的越界钳制检测与新帖入库逻辑（离线测试）。"""
import sys
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import AppConfig  # noqa: E402
from src.discover import discover_digest_all  # noqa: E402


def _row_html(tid: int, fid: int = 58) -> str:
    return (
        f'<tr class="tr3 t_one"><td><a href="read.php?tid={tid}">'
        f'<img src="images/wind/thread/topichot.gif"></a></td>'
        f'<td id="td_{tid}">'
        '<img class="fr" src="images/wind/file/digest_2.gif" title="精华帖标志" />'
        f'<h3><a href="read.php?tid={tid}" id="a_ajax_{tid}">精华案例{tid}</a></h3></td>'
        f'<td class="tal y-style"><a href="u.php?action=show&uid={tid % 10 + 6000}" class="bl">专家{tid % 10 + 6000}</a>'
        '<div class="f10 gray2">2024-01-02</div></td>'
        '<td class="tal y-style f10"><span class="s8">5</span> / 100</td></tr>'
    )


def _page(tid_list: list[int], fid: int = 58) -> str:
    body = "".join(_row_html(t, fid) for t in tid_list)
    return f"<html><body><table>{body}</table></body></html>"


class FakeSession:
    """按 URL 序列返回预置页面；记录请求过的 URL。"""

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages
        self.requested: list[str] = []

    def get_bytes(self, url: str) -> SimpleNamespace:  # noqa: D102
        self.requested.append(url)
        body = self._pages.get(url, "<html><body><table></table></body></html>")
        return SimpleNamespace(status=200, body=body.encode("gb18030"))

    def _alerts_note(self, *a: object) -> None:  # 防御性占位
        pass


def _cfg(tmp: Path) -> AppConfig:
    return AppConfig.model_validate({
        "target": {
            "base_url": "http://test", "mirror_url": "http://mirror",
            "boards": [58], "crawl_order": [58], "corpus_boards": [],
            "moderators": ["灵珠子"], "known_uids": {"灵珠子": 1},
            "digest_search_expected": {}, "expected_min_threads": 0,
        },
        "http": {"user_agent": "test/1.0", "ca_bundle": None},
        "paths": {"db_path": str(tmp / "t.sqlite"), "manifest_csv": str(tmp / "m.csv"),
                  "logs_dir": str(tmp / "logs")},
        "license_note": "测试",
    })


def test_digest_all_clamped_page_detection() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cfg = _cfg(tmp)
        # 页1: 50 帖（此处缩略为 3），页2: 3 个新帖，页3: 与页2 相同（钳制）→ 应停
        p1 = _page([1, 2, 3])
        p2 = _page([4, 5, 6])
        sess = FakeSession({
            "http://test/thread.php?fid=58&search=digest&page=1": p1,
            "http://test/thread.php?fid=58&search=digest&page=2": p2,
            "http://test/thread.php?fid=58&search=digest&page=3": p2,   # 钳制
        })
        stats = discover_digest_all(
            sess, cfg, max_pages_per_board=10, roster_csv=tmp / "roster.csv"
        )
        assert stats[58] == (6, 2), f"期望 6 新帖/2 页，得到 {stats[58]}"
        # 钳制页不应产生第 3 次有效翻页（第 3 请求发出后停止）
        assert len([u for u in sess.requested if "page=3" in u]) == 1
        # 入库验证
        con = sqlite3.connect(tmp / "t.sqlite")
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT tid, in_scope, is_digest, discover_source, crawl_status "
            "FROM thread_index ORDER BY tid"
        ).fetchall()
        assert [r["tid"] for r in rows] == [1, 2, 3, 4, 5, 6]
        assert all(r["in_scope"] == 1 and r["is_digest"] == 1 for r in rows)
        assert all(r["discover_source"] == "digest_all" for r in rows)
        assert all(r["crawl_status"] == "PENDING" for r in rows)
        # 专家名册
        import csv

        with open(tmp / "roster.csv", encoding="utf-8") as f:
            r = list(csv.reader(f))
        assert r[0] == ["uid", "用户名", "精华帖数"]
        assert len(r) == 7  # 表头 + 6 位作者（uid=6001..6006 各 1 帖）


def test_digest_all_existing_thread_keeps_source() -> None:
    """已存在的版主精华帖：只补 in_scope，不覆盖 discover_source。"""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cfg = _cfg(tmp)
        from src.db import connect

        con = connect(tmp / "t.sqlite")     # 先建 Schema 再预置版主精华帖
        con.execute(
            "INSERT INTO thread_index(tid, subject, fid, author_uid, is_digest,"
            " discover_source, crawl_status, in_scope, license_note) "
            "VALUES (999, '版主精华', 58, 1, 1, 'fid_listing', 'DONE', 1, '测试')"
        )
        con.commit()
        con.close()
        sess = FakeSession({
            "http://test/thread.php?fid=58&search=digest&page=1": _page([999, 1000]),
        })
        stats = discover_digest_all(sess, cfg, max_pages_per_board=5)
        # 999 已存在不重复计新帖；1000 新增
        assert stats[58] == (1, 1)
        con = sqlite3.connect(tmp / "t.sqlite")
        con.row_factory = sqlite3.Row
        r999 = con.execute("SELECT * FROM thread_index WHERE tid=999").fetchone()
        assert r999["discover_source"] == "fid_listing"      # 未被覆盖
        assert r999["crawl_status"] == "DONE"                 # 未被重置
        r1000 = con.execute("SELECT * FROM thread_index WHERE tid=1000").fetchone()
        assert r1000["discover_source"] == "digest_all"
        assert r1000["crawl_status"] == "PENDING"
