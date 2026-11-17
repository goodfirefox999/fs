# -*- coding: utf-8 -*-
"""§7.4 衍生资产批处理：路径规则、单图产出、断点续传的选取逻辑。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import marks_batch  # noqa: E402

FIX = Path(__file__).parent / 'fixtures'
BASE = FIX / 'tid163913_p1_marks.jpg'


def test_asset_paths_sibling_naming() -> None:
    """衍生资产与 .meta.json 同名同目录，不新建子目录。"""
    jpg = Path('/x/01_4_1_abc.jpg')
    gj, pv = marks_batch.asset_paths(jpg)
    assert gj == Path('/x/01_4_1_abc.marks.geojson')
    assert pv == Path('/x/01_4_1_abc.marks_preview.png')


def test_process_one_writes_geojson_and_counts() -> None:
    """单图跑完要落 geojson，并把 counts/extra 写进 properties 供回填用。"""
    import shutil
    tmp = Path('/tmp/_marks_batch_case.jpg')
    shutil.copy(BASE, tmp)
    out = marks_batch._process_one((str(tmp), 'marks', True, False))
    assert out['status'] == 'ok', out
    assert out['counts']['yellow'] == 2
    gj = Path(out['geojson'])
    assert gj.exists()
    doc = json.loads(gj.read_text(encoding='utf-8'))
    assert doc['properties']['counts']['yellow'] == 2
    assert doc['properties']['counts']['cyan'] == 5
    assert out['preview'] is True
    gj.unlink(missing_ok=True)
    tmp.with_suffix('.marks_preview.png').unlink(missing_ok=True)
    tmp.unlink(missing_ok=True)


def test_process_one_reports_unreadable() -> None:
    """坏图不能抛异常打断整批，要转成 status=error。"""
    bad = Path('/tmp/_marks_bad.jpg')
    bad.write_bytes(b'not a jpeg')
    out = marks_batch._process_one((str(bad), 'marks', True, False))
    assert out['status'] == 'error' and 'unreadable' in out['error']
    bad.unlink(missing_ok=True)


def test_select_targets_skips_already_done() -> None:
    """断点续传：已有 marks_geojson_path 的行不再入选，--force 才重算。"""
    jpg = Path('/tmp/_marks_sel_a.jpg')
    jpg.write_bytes(BASE.read_bytes())
    con = sqlite3.connect(':memory:')
    con.execute("CREATE TABLE image_asset(image_id TEXT PRIMARY KEY, tid INT, author_uid INT, "
                "position_index INT, download_status TEXT, local_full_path TEXT, "
                "marks_geojson_path TEXT)")
    con.execute("INSERT INTO image_asset VALUES('a',1,1,1,'DONE',?,NULL)", (str(jpg),))
    assert len(marks_batch.select_targets(con, None, None, None, force=False)) == 1
    con.execute("UPDATE image_asset SET marks_geojson_path='/x/a.marks.geojson'")
    assert marks_batch.select_targets(con, None, None, None, force=False) == []
    assert len(marks_batch.select_targets(con, None, None, None, force=True)) == 1
