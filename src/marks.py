# -*- coding: utf-8 -*-
"""卫星图人工标注色分割（文档 §7.4）。

三类标注色的判别策略（HSV，OpenCV 尺度 H 0~179 / S,V 0~255）：
- 黄（穴星/穴位圈）：H 20~35, S>120, V>150 色门 + 环状判据（拟合椭圆的"中空度"：
  墨迹面积 / 椭圆面积 很小，且墨迹沿椭圆周向覆盖率足够）。黄色在本语料里还大量
  用于标题文字与论坛水印，故先做字形聚类，成串的黄色块记为 text 而非穴位圈。
- 青（水系线）：H 85~105, S>80, V>120 + 笔画细长度筛选 → LineString。
- 白（山脊/龙脉线）：文档阈值 S<40, V>220 单独用会把自然地物整片吃进来（实测单图
  近白像素可达画面 47%），因此叠加 V 通道白顶帽，只保留局部显著提亮的细亮笔画。

两道噪声门控：
1. 图像类型门控（applicable）：古籍扫描页/黑白示意图没有标注色语义，直接跳过不归类。
   实测语料里 fid=24 混有整页书扫（白纸黑线），近白像素占 47%，会被误判成白色龙脉线。
2. 干扰区（zone）：Google Earth 底栏与指南针、论坛水印、图内嵌图多在画面边缘，
   落在这些区的检测记 zone≠content，不计入数量。

输出像素坐标（原点左上）与图片尺寸，不做地理配准（为后续配准留接口）。
形态存疑时置 uncertain=true，不强行归类。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

MIN_YELLOW_AREA = 60
MIN_RING_AREA = 45          # px，小号穴位圈（14x11 空心）墨迹仅约 45
MAX_YELLOW_FRAC = 0.10
MIN_LINE_LEN = 60
MIN_LINE_ASPECT = 5.0       # 文档 §7.4：细长轮廓长宽比 > 5。
                            # 漏掉这道门时 29,512 条"白线"里有 19,273 条长宽比 < 3——
                            # 全是白石板/反光/挂布这类方形色块，PCA 仍能硬拟合出斜线。
EDGE_WATERMARK_FRAC = 0.06  # 黄色环中心离左右边缘 < 6% 画面宽 → 竖排水印字圈
                            # （实测 tid=96363 右缘一列"龍行天下風水論壇"字圈，x/W=0.95）
MAX_LINE_THICK = 16
TOPHAT_K = 21               # 白顶帽结构元：大于此尺度的亮区算地物，不算笔画
TOPHAT_MIN = 36             # 局部提亮幅度下限
MIN_RING_SIDE = 14          # px，手绘穴位圈最小直径（实测真有 14px 的小穴位圈）
BIG_RING_SIDE = 38          # px，分界：≥此值当"标注椭圆"直接认；小于此值要求"孤立"才算。
                            # 依据：汉字里「回/田/國/園/圖」自带封闭笔画，单字 14~30 px 会被判成环，
                            # 实测 664 个环里 581 个落在 10~29 px 全是这类字；但它们永远成排出现，
                            # 而真小圈（基准帖 14px 那个）孤零零落在山脊上
MAX_RING_SIDE = 260         # px，超过此尺寸不像一个穴位圈
RING_MAX_THIN = 0.60        # 中空度上限：墨迹/椭圆面积。细线环 0.15，环+圈内文字合并约 0.55，
                            # 实心色块 ≈1.0。上限放在 0.60 是因为"穴星"两字常与环粘连成一个连通域
RING_MIN_COV = 0.55         # 周向覆盖率下限（36 分箱），环要"绕得住一圈"
RING_MAX_RDEV = 0.20        # 归一化半径偏离，环的墨迹应贴在同一条椭圆上；实心块的墨迹散在内部，偏离约 0.3
YELLOW_OVERLAY_FRAC = 0.06  # 黄像素占画面比例上限：超过即整图铺了黄色水印/网格
MAX_RINGS_PER_IMAGE = 6     # 单图环数上限：真实案例帖一图 1~3 个穴星圈（最多 5），
                            # 实测 ≥6 的全是"灵珠子摄"水印字圈（一图 15 个）
MAX_RING_STROKE = 2.2       # px，手绘标注的线宽上限。实测真穴星圈 1.30~1.48，
                            # 金色装饰圆 2.83~7.46、水印字圈 2.72~5.09 —— 线宽是最干净的一刀


# ---------- 类型门控 ----------

def classify(bgr: np.ndarray) -> dict[str, Any]:
    """判断图片是否具备标注色语义。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[..., 1].astype(float), hsv[..., 2].astype(float)
    gray = (s < 30).mean()
    near_white = (v > 200).mean()
    near_black = (v < 60).mean()
    mean_sat = float(s.mean())
    if mean_sat < 26 and near_white > 0.30 and near_black > 0.03:
        return {'applicable': False, 'kind': 'scan_or_chart',
                'mean_sat': round(mean_sat, 1), 'gray_frac': round(float(gray), 3)}
    if mean_sat < 12:
        return {'applicable': False, 'kind': 'monochrome',
                'mean_sat': round(mean_sat, 1), 'gray_frac': round(float(gray), 3)}
    return {'applicable': True, 'kind': 'imagery',
            'mean_sat': round(mean_sat, 1), 'gray_frac': round(float(gray), 3)}


# ---------- 干扰区 ----------

def zone_of(c: dict[str, Any], W: int, H: int) -> str:
    x, y, w, h = c['x'], c['y'], c['w'], c['h']
    cx, cy = x + w / 2, y + h / 2
    if cy > 0.90 * H and w > 0.25 * W:
        return 'ge_bottom_bar'          # Google Earth 拍摄日期/坐标条
    if cy > 0.84 * H and cx > 0.62 * W:
        return 'watermark_br'           # 论坛/作者水印（靈珠子攝 等）
    if cy < 0.10 * H and cx < 0.14 * W:
        return 'logo_tl'                # 左上角水印
    if cy < 0.28 * H and cx > 0.86 * W:
        return 'ge_nav'                 # 右上罗盘/视图控件
    if cy < 0.13 * H and w > 0.30 * W:
        return 'title_band'             # 顶部黄色标题字
    del cx, cy
    return 'content'


# ---------- 掩膜 ----------

def _open(mask: np.ndarray, k: int) -> np.ndarray:
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))


def _close(mask: np.ndarray, k: int) -> np.ndarray:
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))


def _yellow_mask(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    """文档 §7.4 色域：H 20~35, S>120, V>150。

    两个坑都在这条线上，别再往回改：

    1) 不做开运算。基准帖 tid=163913 的穴星圈是压在山体上的 1 px 细椭圆（截图 1200x675
       上外径约 62x50），3x3 开运算会把整圈抹掉——实测该图黄像素 1200→632、环彻底消失，
       这就是"黄圈数全为 0"的直接原因。开运算换闭运算（3x3），只补抗锯齿断点，不削笔画。
    2) 不收紧饱和度。环上线像素 S 中位约 235、p10 约 149，收 S>190 会开始吃环；
       稻田/成片黄块改由"中空度"判据排除（见 _is_ring）。
    """
    gate = ((h >= 20) & (h <= 35) & (s > 120) & (v > 150)).astype(np.uint8) * 255
    return _close(gate, 3)


def _cyan_mask(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    """青（水系线）：H 85~105, S>130, V>120。

    文档原写 S>80，实测会把山脊与天空交界处的青灰雾霭整片吃进来：基准图里那类伪线的
    S 均值仅 90~101、H 均值 103~105，而作者手绘的沅江线 S 均值 145~239、H 均值 90。
    饱和度门槛抬到 130 正好把两者切开（01 图：伪线全灭，真线 5 段全留）。
    形态学同样只做闭运算——沅江线是 1 px 细线，开运算会整条抹掉。
    """
    gate = ((h >= 85) & (h <= 105) & (s > 130) & (v > 120)).astype(np.uint8) * 255
    return _close(gate, 3)


def _red_mask(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    lo1 = ((h <= 8) & (s > 140) & (v > 120))
    lo2 = ((h >= 172) & (s > 140) & (v > 120))
    return _open((lo1 | lo2).astype(np.uint8) * 255, 3)


def _white_mask(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    near = ((s < 40) & (v > 220)).astype(np.uint8) * 255
    tophat = cv2.morphologyEx(v, cv2.MORPH_TOPHAT,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                        (TOPHAT_K, TOPHAT_K)))
    thin_bright = cv2.threshold(tophat, TOPHAT_MIN, 255, cv2.THRESH_BINARY)[1]
    m = _open(cv2.bitwise_and(near, thin_bright), 3)
    return cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))


def _ellipse_features(pts: np.ndarray) -> dict[str, Any]:
    """对连通域像素拟合椭圆，给出"中空度/周向覆盖率/半径偏离"。

    手绘圈常是 1 px 细线且被文字、箭头打断，外轮廓填洞（hole_frac）在断环上会失效
    （实测断环 hole_frac=0，闭环 hole_frac>0.45）。所以另算一组不依赖闭合性的量：

    - thin  中空度 = 墨迹像素数 / 拟合椭圆面积。细线环 0.10~0.20，实心字块 ≈1。
    - cov   周向覆盖率 = 落在椭圆环带（0.72~1.35 倍半径）的墨迹占满 36 个角度分箱的比例。
            文字块墨迹散在椭圆内部，覆盖率低（实测"父母山"0.22）。
    - rdev  归一化半径的平均偏离，环的墨迹应贴在同一条椭圆上（实测 0.15）。
    """
    if len(pts) < 20:
        return {'thin': 9.9, 'cov': 0.0, 'rdev': 9.9, 'axes': (0.0, 0.0), 'center': (0.0, 0.0)}
    (cx, cy), (d1, d2), ang = cv2.fitEllipse(pts.astype(np.float32).reshape(-1, 1, 2))
    a, b = max(d1, d2) / 2.0, max(min(d1, d2) / 2.0, 1e-6)
    th = np.deg2rad(ang)
    dx, dy = pts[:, 0] - cx, pts[:, 1] - cy
    u = (dx * np.cos(th) + dy * np.sin(th)) / a
    w = (-dx * np.sin(th) + dy * np.cos(th)) / b
    r = np.hypot(u, w)
    band = (r > 0.72) & (r < 1.35)
    out = {'thin': len(pts) / max(float(np.pi * a * b), 1.0), 'cov': 0.0, 'rdev': 9.9,
           'axes': (float(2 * a), float(2 * b)), 'center': (float(cx), float(cy)),
           'angle': float(ang)}
    if band.sum() >= 15:
        theta = np.arctan2(w[band], u[band])
        bins = np.unique(((theta + np.pi) / (2 * np.pi) * 36).astype(int) % 36)
        out['cov'] = len(bins) / 36.0
        out['rdev'] = float(np.mean(np.abs(r[band] - 1.0)))
    return out


def _ring_zone(c: dict[str, Any], W: int, H: int, color: str) -> str:
    """环的干扰区判定：在 zone_of 之上补一条"画面下方居中水印带"。

    作者水印"灵珠子 摄影 / 龙行天下风水论坛"固定在画面下方居中，字圈是细黄线，
    线宽/中空度与真穴星圈完全重叠，只有位置能分开。实测 711 个环里 66% 落在 y/H≥0.8、
    x/W≈0.47，就是这条水印带。

    **只对黄色点生效**：沅江青线本来就走画面下方，套用这条会把整条河判成水印。
    """
    z = zone_of(c, W, H)
    if z != 'content' or color != 'yellow':
        return z
    cx, cy = c['x'] + c['w'] / 2.0, c['y'] + c['h'] / 2.0
    if cx < EDGE_WATERMARK_FRAC * W or cx > (1.0 - EDGE_WATERMARK_FRAC) * W:
        return 'watermark_edge'         # 竖排水印字（画面左右边缘）
    if cy > 0.78 * H and 0.25 * W < cx < 0.75 * W:
        return 'watermark_bottom'
    return 'content'


def _components(mask: np.ndarray) -> list[dict[str, Any]]:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, hgt, area = (int(t) for t in stats[i])
        if area < 30 or w < 2 or hgt < 2:
            continue
        sub = (labels[y:y + hgt, x:x + w] == i).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        local = max(cnts, key=cv2.contourArea)
        # findContours 给的是 bbox 局部坐标，质心/几何一律要搬回图像坐标，
        # 否则所有点都会落在画面左上角（老版本实测 ring @[23.2,23.5] 即此 bug）。
        outer = local + np.array([[[x, y]]], dtype=local.dtype)
        perim = float(cv2.arcLength(local, True))
        filled = np.zeros_like(sub)
        cv2.drawContours(filled, [local], -1, 255, cv2.FILLED)
        enclosed = int((filled > 0).sum())
        ys, xs = np.where(sub > 0)
        ell = _ellipse_features(np.column_stack([xs + x, ys + y]).astype(float))
        out.append({'label': i,
                    'x': x, 'y': y, 'w': w, 'h': hgt, 'area': int(area), 'contour': outer,
                    'perimeter': perim, 'contour_area': float(cv2.contourArea(outer)),
                    'thickness': area / max(perim / 2.0, 1.0),
                    # 中空度（闭合环路径）：细闭合圈接近 1，实心色块接近 0
                    'hole_frac': max(enclosed - area, 0) / max(enclosed, 1),
                    'aspect': max(w, hgt) / max(min(w, hgt), 1),
                    'ell': ell})
    return out


def _is_ring(c: dict[str, Any]) -> bool:
    """环判定：闭合环走 hole_frac，被打断的细环走椭圆中空度。

    两条路都必须"绕得住一圈"，否则文字块会被误判（实测"父母山"中空度 0.18 但覆盖率仅 0.22）。
    """
    if c['aspect'] >= 3.5:
        return False
    if c['thickness'] > MAX_RING_STROKE:
        return False                      # 粗笔画/金色装饰/水印字圈，不是手绘细线
    if c['hole_frac'] > 0.45 and c['aspect'] < 3.4:
        return True
    e = c['ell']
    return bool(e['thin'] < RING_MAX_THIN and e['cov'] >= RING_MIN_COV
                and e['rdev'] < RING_MAX_RDEV)


def _inside(c: dict[str, Any], ring: dict[str, Any], slack: float = 1.15) -> bool:
    """点是否落在环拟合椭圆内（用于把环内文字认作环的标签，不单独出点）。"""
    e = ring['ell']
    cx, cy = e['center']
    a, b = e['axes'][0] / 2.0, e['axes'][1] / 2.0
    if a < 1 or b < 1:
        return False
    th = np.deg2rad(e['angle'])
    m = cv2.moments(c['contour'])
    if m['m00'] == 0:
        return False
    px, py = m['m10'] / m['m00'], m['m01'] / m['m00']
    dx, dy = px - cx, py - cy
    u = (dx * np.cos(th) + dy * np.sin(th)) / a
    w = (-dx * np.sin(th) + dy * np.cos(th)) / b
    return bool(u * u + w * w <= slack * slack)


def _center_of(c: dict[str, Any]) -> tuple[float, float]:
    m = cv2.moments(c['contour'])
    if m['m00'] == 0:
        return float(c['x'] + c['w'] / 2), float(c['y'] + c['h'] / 2)
    return float(m['m10'] / m['m00']), float(m['m01'] / m['m00'])


def _watermark_ids(rings: list[dict[str, Any]]) -> set[int]:
    """同径、成串、排布紧凑的一批环＝论坛水印（"龍行天下風水論壇"每字套一个小黄圈）。

    实测两张误检图各 12 个环，直径 14~18 px、彼此间距 < 2.5 倍直径；真实穴位圈一张图
    通常 1~2 个且尺寸差得远（基准帖 01 图是 62 px 的大椭圆 + 14 px 的小圆，直径差 4 倍）。
    所以按"直径相近 + 互相靠近"做单链聚类，簇内 ≥3 个即判水印。
    """
    ids: set[int] = set()
    used: set[int] = set()
    for i, a in enumerate(rings):
        if i in used:
            continue
        group, stack = [], [i]
        while stack:
            k = stack.pop()
            if k in used:
                continue
            used.add(k)
            group.append(k)
            dk = max(rings[k]['w'], rings[k]['h'])
            xk, yk = _center_of(rings[k])
            for j, b in enumerate(rings):
                if j in used:
                    continue
                dj = max(b['w'], b['h'])
                if min(dk, dj) / max(dk, dj) < 0.7:
                    continue
                xj, yj = _center_of(b)
                if np.hypot(xk - xj, yk - yj) < 2.5 * max(dk, dj):
                    stack.append(j)
        if len(group) >= 3:
            ids.update(id(rings[k]) for k in group)
    return ids


def _glyph_clusters(comps: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """把同一行、间距近的黄块并成文字串（标题/说明字）。"""
    if not comps:
        return []
    med_h = float(np.median([c['h'] for c in comps]))
    comps = sorted(comps, key=lambda c: (c['y'] // max(med_h, 1), c['x']))
    clusters: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    for c in comps:
        if cur:
            p = cur[-1]
            same_row = abs((c['y'] + c['h'] / 2) - (p['y'] + p['h'] / 2)) < med_h * 0.9
            close = c['x'] - (p['x'] + p['w']) < med_h * 1.2
            if same_row and close:
                cur.append(c)
                continue
            clusters.append(cur)
        cur = [c]
    if cur:
        clusters.append(cur)
    return clusters


def _centerline(pts: np.ndarray, bins: int = 24) -> list[list[float]]:
    if len(pts) < 8:
        return []
    mean = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - mean, full_matrices=False)
    proj = (pts - mean) @ vt[0]
    perp = (pts - mean) @ vt[1]
    lo, hi = float(proj.min()), float(proj.max())
    if hi - lo < MIN_LINE_LEN:
        return []
    step = (hi - lo) / bins
    line: list[list[float]] = []
    for i in range(bins + 1):
        cut = lo + i * step
        sel = np.abs(proj - cut) <= step * 0.75
        if sel.sum() < 3:
            continue
        p = mean + vt[0] * cut + vt[1] * float(np.median(perp[sel]))
        line.append([round(float(p[0]), 1), round(float(p[1]), 1)])
    return line if len(line) >= 2 else []


def _markers(mask: np.ndarray, color: str, W: int, H: int) -> list[dict[str, Any]]:
    """圈/箭头/字串检测：先按中空度挑出环，再对余下色块做字形聚类。"""
    max_side = min(MAX_RING_SIDE, 0.30 * min(W, H))
    comps = [c for c in _components(mask)
             if c['area'] >= MIN_RING_AREA and max(c['w'], c['h']) <= max_side
             and c['area'] <= MAX_YELLOW_FRAC * W * H]
    rings = [c for c in comps if _is_ring(c)]
    wm = _watermark_ids(rings)
    ring_ids = {id(c) for c in rings}
    # 环内的字（如"穴星"写在圈里）是环的标签，不单独出点，避免同一标注重复计数
    rest = [c for c in comps
            if id(c) not in ring_ids and not any(_inside(c, r) for r in rings)]
    feats = []
    for c in rings:
        m = cv2.moments(c['contour'])
        if m['m00'] == 0 or c['contour_area'] <= 0:
            continue
        cx, cy = m['m10'] / m['m00'], m['m01'] / m['m00']
        fill = c['area'] / max(c['contour_area'], 1.0)
        circ = 4 * np.pi * c['contour_area'] / max(c['perimeter'] ** 2, 1.0)
        shape = 'watermark' if id(c) in wm else 'ring'
        feats.append({'kind': 'point', 'color': color,
                      'geometry': {'type': 'Point',
                                   'coordinates': [round(float(cx), 1),
                                                   round(float(cy), 1)]},
                      'properties': {'shape': shape, 'area_px': c['area'],
                                     'ring_fill_ratio': round(float(fill), 3),
                                     'hole_frac': round(float(c['hole_frac']), 3),
                                     'ellipse_thin': round(float(c['ell']['thin']), 3),
                                     'ellipse_coverage': round(float(c['ell']['cov']), 3),
                                     'ellipse_rdev': round(float(c['ell']['rdev']), 3),
                                     'outer_circularity': round(float(circ), 3),
                                     'diameter_px': int(max(c['w'], c['h'])),
                                     'aspect': round(c['aspect'], 2),
                                     'zone': _ring_zone(c, W, H, color),
                                     'uncertain': False}})
    rest = [c for c in rest if c['area'] >= MIN_YELLOW_AREA]
    for cl in _glyph_clusters(rest):
        if len(cl) >= 3:                       # 一串同色块＝文字（标题/说明字）
            xs = [c['x'] for c in cl]
            ys = [c['y'] for c in cl]
            xe = [c['x'] + c['w'] for c in cl]
            ye = [c['y'] + c['h'] for c in cl]
            box = {'x': min(xs), 'y': min(ys), 'w': max(xe) - min(xs),
                   'h': max(ye) - min(ys)}
            feats.append({'kind': 'text', 'color': color,
                          'geometry': {'type': 'Point', 'coordinates': [
                              round((min(xs) + max(xe)) / 2, 1),
                              round((min(ys) + max(ye)) / 2, 1)]},
                          'properties': {'shape': 'text_run', 'glyphs': len(cl),
                                         'bbox': [min(xs), min(ys), max(xe), max(ye)],
                                         'zone': zone_of(box, W, H),
                                         'uncertain': False}})
            continue
        for c in cl:
            m = cv2.moments(c['contour'])
            if m['m00'] == 0 or c['contour_area'] <= 0:
                continue
            cx, cy = m['m10'] / m['m00'], m['m01'] / m['m00']
            fill = c['area'] / max(c['contour_area'], 1.0)   # 环：≪1；实心：≈1
            shape = 'arrow' if c['aspect'] > 3.0 else 'blob'
            feats.append({'kind': 'point', 'color': color,
                          'geometry': {'type': 'Point',
                                       'coordinates': [round(float(cx), 1),
                                                       round(float(cy), 1)]},
                          'properties': {'shape': shape, 'area_px': c['area'],
                                         'ring_fill_ratio': round(float(fill), 3),
                                         'hole_frac': round(float(c['hole_frac']), 3),
                                         'ellipse_thin': round(float(c['ell']['thin']), 3),
                                         'ellipse_coverage': round(float(c['ell']['cov']), 3),
                                         'aspect': round(c['aspect'], 2),
                                         'zone': zone_of(c, W, H),
                                         'uncertain': True}})
    # 环紧挨着别的黄色字形（同一基线 ±0.6d、水平 2.5d 内）→ 是"把字圈起来"，不是穴位标记。
    # 依据：人工复核 tid=4232/140413/51409/90805/91763/108153/109146/128981/133532 九张，
    # 9/9 都是作者给标注文字里的单个字加圈（或水印字圈），环旁边就挨着同排黄字。
    # 真穴星圈是孤零零落在山体上的（基准帖 01 图：环内两字被吸收，四周 95px 内无同排字）。
    if color == 'yellow':
        pts = [f for f in feats if f['geometry']['type'] == 'Point'
               and f['properties'].get('shape') in ('blob', 'arrow', 'text_run', 'ring')]
        for f in feats:
            pr = f['properties']
            if pr.get('shape') != 'ring':
                continue
            cx, cy = f['geometry']['coordinates']
            d = pr['diameter_px']
            # 邻居要在"变异前"的集合里找：一排字圈会互相确认，
            # 边改边查会让最后剩下那个"看起来孤立"的漏网（实测 tid=4232 就这样漏过 1 个）
            neighbour = False
            for g in pts:
                if g is f:
                    continue
                gx, gy = g['geometry']['coordinates']
                # 小圈按 4d/1.0d 找邻居：字圈之间常隔着一个空格，
                # 2.5d 太紧（实测 tid=140413 两个相距 52px 的 17px 字圈互不认账）
                if abs(gy - cy) < 1.0 * d and 0 < abs(gx - cx) < 4.0 * d:
                    neighbour = True
                    break
            # 大圈也过一遍邻居判据：水印字「灵珠子摄影」在 1200px 图上就有 40px 高，
            # 单靠尺寸放过它。真标注椭圆（基准帖 62px）离最近的同排字有 88px，够远。
            if neighbour:                     # 成排＝汉字笔画/水印字（回/田/國/園/灵/珠）
                pr['shape'] = 'watermark'
                pr['watermark_reason'] = 'char_in_text'

    # 环紧贴同色文字串（≤2d，含上下方向）→ 给标题/水印里的字加圈，不是穴位标记。
    # 实测 tid=35588 水印「灵珠子摄影」的「子」、tid=73679 同一串里的字圈都属此类；
    # 基准帖 62px 穴星圈离「父母山」标题约 2.3d，正好在门外。
    runs = [f['properties']['bbox'] for f in feats
            if f['color'] == color and f['properties'].get('shape') == 'text_run']
    for f in feats:
        pr = f['properties']
        if pr.get('shape') != 'ring':
            continue
        cx, cy = f['geometry']['coordinates']
        d = pr['diameter_px']
        for b in runs:
            dx = max(b[0] - cx, 0.0, cx - b[2])
            dy = max(b[1] - cy, 0.0, cy - b[3])
            if (dx * dx + dy * dy) ** 0.5 <= 2.0 * d:
                pr['shape'] = 'watermark'
                pr['watermark_reason'] = 'char_near_text'
                break

    return feats


def _lines(mask: np.ndarray, color: str, labels: np.ndarray,
           W: int, H: int, min_len: int = MIN_LINE_LEN,
           min_aspect: float = MIN_LINE_ASPECT) -> list[dict[str, Any]]:
    feats = []
    for c in _components(mask):
        long_side = max(c['w'], c['h'])
        if (long_side < min_len or c['thickness'] > MAX_LINE_THICK
                or c['aspect'] < min_aspect):
            continue
        # 只取本连通域的像素（==label）。老写法用 >0，会把 bbox 内其它连通域的
        # 像素也算进中心线——两条线交叉时骨架会跳到另一条线上。
        ys, xs = np.where(labels[c['y']:c['y'] + c['h'],
                                  c['x']:c['x'] + c['w']] == c['label'])
        if len(ys) == 0:
            continue
        # 同 _components：labels 切片给的是 bbox 局部坐标，中心线必须搬回图像坐标，
        # 否则所有线都堆在左上角（实测沅江 5 段全叠在原点附近，预览图完全错位）。
        pts = np.column_stack([xs + c['x'], ys + c['y']]).astype(float)
        coords = _centerline(pts)
        if len(coords) < 2:
            continue
        feats.append({'kind': 'line', 'color': color,
                      'geometry': {'type': 'LineString', 'coordinates': coords},
                      'properties': {'length_px': round(float(long_side), 1),
                                     'thickness_px': round(float(c['thickness']), 2),
                                     'aspect': round(c['aspect'], 2), 'area_px': c['area'],
                                     'path_points': len(coords),
                                     'zone': zone_of(c, W, H),
                                     'uncertain': bool(c['aspect'] < 8.0
                                                       or c['thickness'] > 10.0)}})
    return feats


def analyze(img_path: Path) -> dict[str, Any]:
    """单图标注分割 → {width,height,kind,counts,features,masks_area_px}。"""
    bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError('unreadable image')
    H, W = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    kind = classify(bgr)
    res: dict[str, Any] = {'width': int(W), 'height': int(H), 'image_kind': kind,
                           'features': [], 'counts': {'yellow': 0, 'white': 0, 'cyan': 0},
                           'masks_area_px': {'yellow': 0, 'white': 0, 'cyan': 0, 'red': 0},
                           'extra': {'red_rings': 0, 'red_lines': 0, 'yellow_nonring': 0,
                                     'text_runs': 0, 'uncertain': 0}}
    if not kind['applicable']:
        return res
    ym, cm, wm, rm = (_yellow_mask(h, s, v), _cyan_mask(h, s, v),
                      _white_mask(h, s, v), _red_mask(h, s, v))
    lab_w = cv2.connectedComponentsWithStats(wm, connectivity=8)[1]
    lab_c = cv2.connectedComponentsWithStats(cm, connectivity=8)[1]
    lab_r = cv2.connectedComponentsWithStats(rm, connectivity=8)[1]
    # 青线是弯曲水系，被文字/箭头切成短段后 bbox 长宽比可低到 2.5（基准帖沅江
    # 104x42 那段就是 2.48），门槛只能放到 2.0；白线按文档严格 >5（白石板/挂布
    # 这类方形亮块必须挡掉）。
    feats = (_markers(ym, 'yellow', W, H) + _markers(rm, 'red', W, H)
             + _lines(wm, 'white', lab_w, W, H)
             + _lines(cm, 'cyan', lab_c, W, H, min_aspect=2.0)
             + _lines(rm, 'red', lab_r, W, H, min_len=40, min_aspect=2.0))

    # 整图铺黄水印（"龍行天下風水論壇"平铺版）：黄像素动辄占画面 5%~30%，
    # 每个水印字都被判成环。基准帖真实标注只占 0.16%，所以按整幅占比一刀切掉。
    overlay = float(ym.sum() / 255) / max(W * H, 1) > YELLOW_OVERLAY_FRAC
    if overlay:
        for f in feats:
            pr = f['properties']
            if f['color'] == 'yellow' and pr.get('shape') == 'ring':
                pr['shape'] = 'watermark'
                pr['watermark_reason'] = 'yellow_overlay'

    # 环数异常：单图 6 个以上黄圈基本不可能是穴星标注。实测 tid=1883 那张
    # "灵珠子摄"水印图有 15 个字圈，直径 13~89 px 参差、中空度全在 0.49~0.60，
    # 与真穴星圈（0.15~0.55）重叠，靠单环特征分不开，只能按"一张照片画不出 6 个穴星"兜底。
    yellow_rings = [f for f in feats
                    if f['color'] == 'yellow' and f['properties'].get('shape') == 'ring']
    if len(yellow_rings) >= MAX_RINGS_PER_IMAGE:
        for f in yellow_rings:
            f['properties']['shape'] = 'watermark'
            f['properties']['watermark_reason'] = 'ring_count_anomaly'

    def _n(color: str, pred: Callable[[dict[str, Any]], bool] = lambda f: True) -> int:
        return sum(1 for f in feats if f['color'] == color
                   and f['properties']['zone'] == 'content' and pred(f))

    def ring(f: dict[str, Any]) -> bool:
        return bool(f['properties'].get('shape') == 'ring')

    def line(f: dict[str, Any]) -> bool:
        return bool(f['kind'] == 'line')

    res['features'] = feats
    res['counts'] = {'yellow': _n('yellow', ring),
                     'white': _n('white'),
                     'cyan': _n('cyan')}
    res['masks_area_px'] = {'yellow': int(ym.sum() / 255), 'white': int(wm.sum() / 255),
                            'cyan': int(cm.sum() / 255), 'red': int(rm.sum() / 255)}
    # 红圈不在文档 §7.4 三分类内，但它是本语料里真实常见的穴位标注 → 只进 geojson/extra
    res['extra'] = {'red_rings': _n('red', ring), 'red_lines': _n('red', line),
                    'yellow_nonring': _n('yellow', lambda f: not ring(f)),
                    'yellow_overlay': bool(overlay),
                    'watermarks': sum(1 for f in feats
                                      if f['properties'].get('shape') == 'watermark'),
                    'text_runs': sum(1 for f in feats
                                     if f['properties'].get('shape') == 'text_run'),
                    'uncertain': sum(1 for f in feats if f['properties']['uncertain'])}
    return res


def to_geojson(res: dict[str, Any], src: str) -> dict[str, Any]:
    return {'type': 'FeatureCollection',
            'crs': {'type': 'name',
                    'properties': {'name': 'urn:ogc:def:crs:undefined::pixel'}},
            'properties': {'source_image': src, 'width_px': res['width'],
                           'height_px': res['height'], 'coordinate_order': 'x,y',
                           'coordinate_origin': 'top-left', 'georeferenced': False,
                           'image_kind': res['image_kind'],
                           'note': '像素坐标，未做地理配准（文档 §7.4 本次范围外）；'
                                   'red 为语料实测补充色，不属于文档三分类'},
            'features': res['features']}


def preview(img_path: Path, res: dict[str, Any], out: Path, max_side: int = 1000) -> None:
    """分割结果叠加图（供人工目视校验）。

    绘制分三档，否则没法目视校验——老版本把所有黄色点都画成粗黄圈，
    一张水印图上几十个"非环色块"看起来跟真穴位圈一模一样：
    - **计数的环**（shape=ring 且在 content 区）：粗圈 + 十字，本色
    - **文字串**：矩形框
    - **未计入的**（blob/arrow/watermark/干扰区）：细线小圈，灰度，一眼能区分
    """
    bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError('unreadable image')
    scale = min(1.0, max_side / max(res['width'], res['height']))
    if scale < 1.0:
        bgr = cv2.resize(bgr, (int(res['width'] * scale), int(res['height'] * scale)),
                         interpolation=cv2.INTER_AREA)
    col_of = {'yellow': (0, 215, 255), 'white': (255, 255, 255),
              'cyan': (255, 40, 40), 'red': (40, 40, 255)}
    for f in res['features']:
        col = col_of[f['color']]
        pr = f['properties']
        counted = pr.get('zone') == 'content' and pr.get('shape') in ('ring', 'line', 'text_run')
        if not counted:
            col = (110, 110, 110)               # 灰细线＝未计入（水印/色块/干扰区）
        if f['geometry']['type'] == 'Point':
            x, y = (int(round(c * scale)) for c in f['geometry']['coordinates'])
            if pr.get('shape') == 'text_run':
                bb = [int(round(c * scale)) for c in pr['bbox']]
                cv2.rectangle(bgr, (bb[0], bb[1]), (bb[2], bb[3]), col, 1)
            elif counted:
                cv2.circle(bgr, (x, y), 16, col, 2)
                cv2.drawMarker(bgr, (x, y), col, cv2.MARKER_CROSS, 14, 2)
            else:
                cv2.circle(bgr, (x, y), 5, col, 1)
        else:
            pts = np.array([[round(c * scale), round(d * scale)]
                            for c, d in f['geometry']['coordinates']],
                           dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(bgr, [pts], False, col, 2 if counted else 1)
    # 按扩展名选编码参数：PNG 不吃 JPEG_QUALITY，混用会刷一堆 imwrite 警告
    if str(out).lower().endswith('.png'):
        cv2.imwrite(str(out), bgr, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    else:
        cv2.imwrite(str(out), bgr, [cv2.IMWRITE_JPEG_QUALITY, 82])
