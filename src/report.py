"""采集报告与质检输出（文档 T10）：Markdown，十节结构。"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _q1(con: Any, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = con.execute(sql, params).fetchone()
    return int(row[0])


def build_report(con: Any, cfg: Any) -> str:
    lines: list[str] = []
    add = lines.append

    add("# 龙行天下论坛·灵珠子精华帖采集报告\n")
    add("> 产出为结构化观测数据，不构成任何吉凶判定结论。\n")

    # 1. 采集概况
    total = _q1(con, "SELECT COUNT(*) FROM thread_index")
    done = _q1(con, "SELECT COUNT(*) FROM thread_index WHERE crawl_status='DONE'")
    failed = _q1(con, "SELECT COUNT(*) FROM thread_index WHERE crawl_status='FAILED'")
    invalid = _q1(con, "SELECT COUNT(*) FROM thread_index WHERE crawl_status='INVALID'")
    pending = _q1(con, "SELECT COUNT(*) FROM thread_index WHERE crawl_status='PENDING'")
    add("## 1. 采集概况\n")
    add(f"- 目标帖数: {total}（成功 {done} / 失败 {failed} / 无效 {invalid} / 待抓 {pending}）")
    add(f"- 付费墙跳过: {_q1(con, 'SELECT COUNT(*) FROM thread_index WHERE paywalled=1')}")
    add(f"- 许可声明: {cfg.license_note}")
    n_scope = _q1(con, "SELECT COUNT(*) FROM thread_index WHERE in_scope=1")
    oos = _q1(con, "SELECT COUNT(*) FROM thread_index WHERE crawl_status='OUT_OF_SCOPE'")
    add(f"- 全站索引总条数: {total}；其中 in_scope {n_scope}；crawl 阶段判 OUT_OF_SCOPE {oos}\n")

    # 1b. 版主发现与 discrepancy（v2 §1.2(4)）
    add("## 1b. 版主发现与 discrepancy\n")
    add("| 版主 | uid | 列表页主题 | 作者搜索 | 精华搜索 | 搜索补标 | 并集 | 备注 |")
    add("|---|---|---|---|---|---|---|---|")
    stats = con.execute(
        "SELECT name, uid, listing_topics, search_topics, search_digest,"
        " search_in_scope, union_topics, discrepancy_note FROM discovery_stats ORDER BY uid"
    ).fetchall()
    for r in stats:
        add(f"| {r['name']} | {r['uid']} | {r['listing_topics']} | {r['search_topics']} "
            f"| {r['search_digest']} | {r['search_in_scope']} | {r['union_topics']} "
            f"| {r['discrepancy_note']} |")
    mods = con.execute("SELECT COUNT(*) FROM moderators").fetchone()[0]
    add(f"\n- 版主 uid 解析: {mods}/{mods}（可解析者全部完成；u.php 登录墙未触碰，"
        f"全部来自列表页被动累积）")
    add("- 阿难: 已按委托人决定永久排除（2026-11-03）——7 版块列表页 0 条同名作者行，"
        "uid 无法被动解析，且明确不绕过登录墙；不计入覆盖率分母\n")

    # 1c. 版块扫描覆盖
    add("## 1c. 版块索引覆盖\n")
    add("| fid | 版块 | 索引主题数 | in_scope | DONE |")
    add("|---|---|---|---|---|")
    for r in con.execute(
        "SELECT COALESCE(fid,-1) AS f, COALESCE(forum_name,'?') AS fn, COUNT(*) AS n, "
        "SUM(in_scope) AS s, SUM(CASE WHEN crawl_status='DONE' THEN 1 ELSE 0 END) AS d "
        "FROM thread_index GROUP BY fid ORDER BY n DESC"
    ).fetchall():
        add(f"| {r['f']} | {r['fn']} | {r['n']} | {r['s'] or 0} | {r['d'] or 0} |")
    add("")

    # 2. 楼层统计
    add("## 2. 楼层统计\n")
    add(f"- 总楼层数: {_q1(con, 'SELECT COUNT(*) FROM floor')}")
    add(f"- 楼主(uid=1)楼层: {_q1(con, 'SELECT COUNT(*) FROM floor WHERE author_uid=1')}")
    add(f"- 跨页帖数(page_count>1): {_q1(con, 'SELECT COUNT(*) FROM thread_index WHERE page_count>1')}")
    add(f"- 最大页数: {_q1(con, 'SELECT MAX(page_count) FROM thread_index')}\n")

    # 3. 结构化模板
    add("## 3. 结构化模板命中率\n")
    for sec_name in ("前言", "数据", "浅析", "历史查证", "后语"):
        n = _q1(con, "SELECT COUNT(*) FROM section WHERE section_name=?", (sec_name,))
        add(f"- 【{sec_name}】段: {n} 帖")
    add(f"- 模板 richness≥3: {_q1(con, 'SELECT COUNT(*) FROM thread_index WHERE template_richness>=3')}\n")

    # 4. 罗盘数据
    add("## 4. 罗盘数据抽取\n")
    n_bo = _q1(con, "SELECT COUNT(*) FROM bearing_observation")
    n_cons = _q1(con, "SELECT COUNT(*) FROM bearing_observation WHERE is_consistent=1")
    add(f"- 总观测值: {n_bo}")
    add(f"- ★ 山名-度数自洽率: {n_cons}/{n_bo}"
        f" = {n_cons/max(1,n_bo):.1%}")
    add(f"- ★ 骑线预警(is_boundary_risk): {_q1(con, 'SELECT COUNT(*) FROM bearing_observation WHERE is_boundary_risk=1')}")
    add(f"- ★ 大空亡预警(is_gua_boundary_risk): {_q1(con, 'SELECT COUNT(*) FROM bearing_observation WHERE is_gua_boundary_risk=1')}")
    add(f"- needs_review: {_q1(con, 'SELECT COUNT(*) FROM bearing_observation WHERE needs_review=1')}")
    add("- category 分布:")
    for cat, n in con.execute(
        "SELECT COALESCE(category,'NULL'), COUNT(*) FROM bearing_observation GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall():
        add(f"  - {cat}: {n}")
    add("- needs_review 样例（前 10，供人工核对）:")
    for row in con.execute(
        "SELECT tid,label,shan24,degree,shan_from_degree,raw_text FROM bearing_observation "
        "WHERE needs_review=1 LIMIT 10"
    ).fetchall():
        add(f"  - tid={row['tid']} | {row['raw_text']} | 文本山={row['shan24']} "
            f"| 度数反推={row['shan_from_degree']} | {row['degree']}度\n")

    # 5. 图片统计
    add("## 5. 图片统计\n")
    n_ia = _q1(con, "SELECT COUNT(*) FROM image_asset")
    n_done = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE download_status='DONE'")
    n_fail = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE download_status='FAILED'")
    n_dead = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE download_status='DEAD'")
    n_skip = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE download_status='SKIPPED_PENDING_AUTHORIZATION'")
    n_gps = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE exif_gps_present=1")
    add(f"- 登记数: {n_ia}")
    add(f"- 已下载: {n_done}")
    add(f"- 失败: {n_fail}")
    add(f"- 死链(DEAD，站点返回空体): {n_dead}")
    if n_fail:
        hosts = Counter(urlparse(u).hostname or '?' for (u,) in con.execute(
            "SELECT full_url FROM image_asset WHERE download_status='FAILED'"))
        own = sum(hosts.get(h, 0) for h in
                  ('www.ok2009ok.com', 'ok2009ok.com', 'www.ok88ok88.com', 'ok88ok88.com'))
        top = ' / '.join(f'{h} {c}' for h, c in hosts.most_common(3))
        add(f"- 失败分布: 本站/镜像 {own} 张，外站图床 {n_fail - own} 张（{top}）")
    add(f"- 授权跳过: {n_skip}")
    add(f"- EXIF 含 GPS: {n_gps}（拍摄设备自带坐标；个人研究用途，不公开分发）\n")

    # 6. 标注分割
    n_gj6 = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE marks_geojson_path IS NOT NULL")
    add("## 6. 标注分割统计\n")
    if n_gj6:
        n_done6 = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE download_status='DONE'")
        n_flag6 = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE "
                           "(marks_yellow_count+marks_white_count+marks_cyan_count)>0")
        n_y6 = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE marks_yellow_count>0")
        s_y6 = _q1(con, "SELECT COALESCE(SUM(marks_yellow_count),0) FROM image_asset")
        s_c6 = _q1(con, "SELECT COALESCE(SUM(marks_cyan_count),0) FROM image_asset")
        s_w6 = _q1(con, "SELECT COALESCE(SUM(marks_white_count),0) FROM image_asset")
        add(f"- 已执行: {n_gj6} 张（占已下图 {n_gj6/max(n_done6,1):.1%}）")
        add(f"- ★ 成功提取标注的图片: {n_flag6}/{n_gj6} = {n_flag6/max(n_gj6,1):.1%}"
            "（黄/白/青三分类至少检出 1 条）")
        add(f"- 黄色穴位圈: {s_y6} 个，分布在 {n_y6} 张图；青色水系线: {s_c6} 条；"
            f"白色山脊线: {s_w6} 条")
        add(f"- 未检出: {n_gj6-n_flag6} 张（无标注的实景照、古籍书扫、纯风景）")
        add("- 口径: 计数为算法候选标注，未经人工逐张确认；黄圈语义最明确，"
            "白线在近景白布/石板上仍可能误检。详见 §7b\n")
    else:
        add("- 未执行（M6 依赖图片下载授权）。\n")

    # 7. 图注-方位绑定
    add("## 7. 图注-方位绑定\n")
    n_link = _q1(con, "SELECT COUNT(*) FROM image_bearing_link")
    n_cap = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE caption_before<>'' OR caption_after<>''")
    add(f"- image_bearing_link 配对数: {n_link}（★核心指标）")
    add(f"- 有图注的图片: {n_cap}\n")

    # 7b. §7.4 衍生资产：颜色分割矢量化
    n_done_img = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE download_status='DONE'")
    n_gj = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE marks_geojson_path IS NOT NULL")
    n_yellow_img = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE marks_yellow_count>0")
    sum_y = _q1(con, "SELECT COALESCE(SUM(marks_yellow_count),0) FROM image_asset")
    sum_c = _q1(con, "SELECT COALESCE(SUM(marks_cyan_count),0) FROM image_asset")
    sum_w = _q1(con, "SELECT COALESCE(SUM(marks_white_count),0) FROM image_asset")
    n_ocr = _q1(con, "SELECT COUNT(*) FROM image_asset WHERE ocr_json_path IS NOT NULL")
    n_prev = 0
    for (p,) in con.execute(
            "SELECT local_full_path FROM image_asset WHERE marks_geojson_path IS NOT NULL"):
        if p and Path(p).with_suffix('.marks_preview.png').exists():
            n_prev += 1
    pct = n_gj / max(n_done_img, 1) * 100
    add("## 7b. 衍生资产：颜色分割（§7.4）\n")
    add(f"- marks.geojson: {n_gj}/{n_done_img} 张已下图（{pct:.1f}%）")
    add(f"- marks_preview.png: {n_prev}/{n_gj} 张（{n_prev/max(n_gj,1):.1%}，供人工目视校验）")
    add(f"- 黄色穴位圈: {sum_y} 个，分布在 {n_yellow_img} 张图")
    add(f"- 青色水系线: {sum_c} 条；白色山脊线: {sum_w} 条")
    add("- 分割口径: 黄 H20~35/S>120/V>150 + 环状判据；青 H85~105/S>130/V>120；"
        "白 S<40/V>220 + V 白顶帽（只留细亮笔画）；线要求长宽比 >5（青线放宽到 2）")
    add("- 水印排除: 底部/左右边缘水印带、成排水印字圈、贴文字串的字圈不计入数量")
    add(f"- ocr.json: {n_ocr} 张（tesseract chi_sim；只收图上黄色标注文字，"
        f"圈内 15~20px 小字识别不可靠未收录）")
    add("- 文件与图片同目录：`<图名>.marks.geojson` / `<图名>.marks_preview.png`\n")

    # 8. 同行评分
    add("## 8. 同行评分统计\n")
    n_ps = _q1(con, "SELECT COUNT(*) FROM peer_score")
    add(f"- 评分记录总数: {n_ps}")
    add("- reason 词频 Top 20:")
    reasons: Counter[str] = Counter()
    for (r,) in con.execute(
        "SELECT reason FROM peer_score WHERE reason IS NOT NULL AND reason<>''"
    ).fetchall():
        reasons[r.strip()] += 1
    for reason, n in reasons.most_common(20):
        add(f"  - {reason}: {n}")
    add("")

    # 9. 反馈记录
    add("## 9. 反馈记录统计\n")
    for ftype in ("A_历史勘验", "B_调理反馈", "C_同行评价"):
        n = _q1(con, "SELECT COUNT(*) FROM feedback_record WHERE feedback_type=?", (ftype,))
        add(f"- {ftype}: {n}")
    add("")

    # 10. 异常与告警
    add("## 10. 异常与告警清单\n")
    alerts_path = cfg.paths.logs_dir / "alerts.log"
    if alerts_path.exists():
        content = alerts_path.read_text(encoding="utf-8").strip()
        if content:
            for ln in content.splitlines()[:50]:
                try:
                    entry = json.loads(ln)
                    add(f"- [{entry.get('kind')}] {entry.get('message')}")
                except Exception:
                    add(f"- {ln[:200]}")
        else:
            add("- 无告警")
    else:
        add("- 无告警")

    # 异常帖
    fails = con.execute(
        "SELECT tid, error_msg FROM thread_index WHERE crawl_status IN ('FAILED','INVALID') LIMIT 20"
    ).fetchall()
    if fails:
        add("\n### 失败/无效帖\n")
        for r in fails:
            add(f"- tid={r['tid']}: {r['error_msg']}")

    return "\n".join(lines) + "\n"
