"""Phase 11 规则生成器（一次性工具，产物入库）：紫白 / 二十八宿 / 吉神 共 10 条。

为什么单独一个文件而不是塞进 ``gen_rules.py``
--------------------------------------------
``gen_rules.py`` 是 41 条基线规则的生成器，它的 ``RULES_SPEC`` 是**首版快照**；
Phase 4-9 的规则包（正五行/三合/董公/玄空/天星/斗首）都是手写入库、没有再回头改
``gen_rules.py``。本文件沿用同一惯例：只负责本轮 10 条，字段模板与基线保持一致
（``status: 待考证``、``citation.quote: null``、tests 命名 ``RT-<rule>-HIT/MISS``）。

**运行后必须人工复核**。Agent 不得自行把 status 改为「已考证」。
用法：``python3 tools/gen_rules_phase11.py``
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "core-rule" / "rules"
CASES = ROOT / "tests" / "cases" / "rule_tests"

HEADER = (
    "# 本文件由 tools/gen_rules_phase11.py 生成，结构统一；规则内容（条件/解释/出处）需人类考证者复核。\n"
    "# status: 待考证 = 口诀常见但原文未核，默认不参与正式判定，命中时仅登记为 unknown。\n"
    "# citation.quote 为 null 表示「尚未核对原文」，不是缺漏，禁止为填满字段而编造引文。\n"
)

BUILD_TASKS = ["动土", "修造", "上梁", "竖柱", "安门", "安灶", "入宅", "安葬", "破土", "立碑", "修坟", "修祠", "安龛", "升座"]

#: 二十八宿「吉宿」十四宿（《玉匣记》系二十八宿值日吉凶歌的大体标签）
XIU_JI = ["角", "房", "尾", "箕", "斗", "室", "壁", "娄", "胃", "毕", "参", "井", "张", "轸"]
#: 二十八宿「凶宿」十四宿（与吉宿互补，两极合计 28）
XIU_XIONG = ["亢", "氐", "心", "牛", "女", "虚", "危", "奎", "昴", "觜", "鬼", "柳", "星", "翼"]


def cite(source: str, *, entry: str | None = None) -> dict:
    return {
        "kind": "classic",
        "source": source,
        "edition": None,
        "juan": None,
        "pian": None,
        "entry": entry,
        "quote_kind": None,
        "quote": None,
        "url_or_path": None,
        "verified_by": None,
        "verified_at": None,
        "confidence": "低",
    }


def rule(
    rule_id: str,
    category: str,
    *,
    severity: str,
    target: str,
    condition: dict,
    explanation: str,
    notes: str,
    source: str,
    entry: str | None = None,
    task_kinds: list[str] | None = None,
    score_weight: float | None = None,
) -> dict:
    return {
        "api_version": 1,
        "rule_id": rule_id,
        "version": 1,
        "school": "public",
        "category": category,
        "status": "待考证",
        "hard_veto": False,
        "severity": severity,
        "target": target,
        "evaluable": True,
        "applies_to": {
            "task_kinds": task_kinds if task_kinds is not None else [],
            "node_kinds": [],
            "strictness_min": "normal",
        },
        "condition": condition,
        "score_weight": score_weight,
        "citation": cite(source, entry=entry),
        "tests": [f"RT-{rule_id}-HIT", f"RT-{rule_id}-MISS"],
        "explanation": explanation,
        "supersedes": None,
        "notes": notes,
    }


RULES_SPEC: list[dict] = [
    # ================= 紫白四盘 =================
    rule(
        "PUB-ZIBAI-MONTH-001", "月五黄到山", severity="慎用", target="mountain",
        condition={"fact": "facts.zibai.month.wuhuang_hit_palace", "op": "eq", "value": True},
        explanation="坐山{site.mountain}恰落本月五黄所在之宫（月紫白逆退入中，顺飞九宫），按本规则判为慎用。",
        notes=(
            "待考证：月紫白以节气月换月是否通书共识；月五黄是否同忌向首；"
            "口径 zibai_fly 只作用于日/时盘，月盘恒顺飞。"
        ),
        source="《象吉通书》", entry="月家紫白", task_kinds=BUILD_TASKS,
    ),
    rule(
        "PUB-ZIBAI-DAY-001", "日五黄到山", severity="慎用", target="mountain",
        condition={"fact": "facts.zibai.day.wuhuang_hit_palace", "op": "eq", "value": True},
        explanation="坐山{site.mountain}恰落日五黄所在之宫，按本规则判为慎用。",
        notes=(
            "待考证：日盘三元边界取「节气后首个甲子日」还是「节气当日换元」；"
            "日盘顺飞/逆飞两说已注册为口径 zibai_fly，换口径会改变本规则结论。"
        ),
        source="《选择求真》", entry="日家三元紫白", task_kinds=BUILD_TASKS,
    ),
    rule(
        "PUB-ZIBAI-HOUR-001", "时五黄到山", severity="慎用", target="hour",
        condition={"fact": "facts.zibai.hour.wuhuang_hit_palace", "op": "eq", "value": True},
        explanation="所择时辰的五黄落于坐山之宫，按本规则判为慎用（时辰层面，弱于日/月层）。",
        notes=(
            "待考证：时紫白以「日支组起星」是否通书共识（另有「日星起时」一说）；"
            "时五黄是否仅忌动作方位、不忌整日。"
        ),
        source="《象吉通书》", entry="时家紫白", task_kinds=BUILD_TASKS,
    ),
    rule(
        "PUB-ZIBAI-JI-001", "年紫白吉星到山", severity="推荐", target="mountain",
        condition={"fact": "facts.zibai.year.shan_star", "op": "in", "value": [1, 6, 8, 9]},
        explanation="坐山所得年紫白为一白/六白/八白/九紫（紫白四吉），按本规则记为正向证据。",
        notes=(
            "待考证：紫白四吉（1/6/8/9）之说见通书；正向证据不等于可用结论，仍须通过否决层。"
            "年紫白以立春换年，跨立春日课结论会变。"
        ),
        source="《象吉通书》", entry="年家紫白", task_kinds=BUILD_TASKS, score_weight=1.0,
    ),
    # ================= 二十八宿值日 =================
    rule(
        "PUB-XIU-XIONG-001", "值日凶宿", severity="慎用", target="day",
        condition={"fact": "facts.xiu.day", "op": "in", "value": XIU_XIONG},
        explanation="用事日值二十八宿之凶宿（{facts.xiu.full_name}），按《玉匣记》系值日吉凶歌判为慎用。",
        notes=(
            "待考证：宿之吉凶标签各本不一（同一宿或标吉而注中另有不宜），"
            "本规则取「大体吉凶」十四/十四两分，不细分事项；"
            "值宿本身是周期算术（facts.xiu.day，星期恒等式自校验），吉凶标签才是断言。"
        ),
        source="《玉匣记》", entry="二十八宿值日吉凶歌",
        task_kinds=["动土", "修造", "上梁", "安门", "安葬", "破土", "立碑", "修坟", "嫁娶", "入宅", "移徙"],
    ),
    rule(
        "PUB-XIU-JI-001", "值日吉宿", severity="可用", target="day",
        condition={"fact": "facts.xiu.day", "op": "in", "value": XIU_JI},
        explanation="用事日值二十八宿之吉宿（{facts.xiu.full_name}），按《玉匣记》系值日吉凶歌记为可用参考。",
        notes=(
            "待考证：吉宿仍有所忌（如角宿吉而忌葬、房宿吉而忌嫁娶，各本互异），"
            "本规则只作正向参考，不作放行依据。"
        ),
        source="《玉匣记》", entry="二十八宿值日吉凶歌",
        task_kinds=["动土", "修造", "上梁", "安门", "安葬", "破土", "立碑", "修坟", "嫁娶", "入宅", "移徙"],
        score_weight=0.5,
    ),
    # ================= 吉神（天德 / 月德 / 月德合 / 天赦）=================
    rule(
        "PUB-TIANDE-001", "天德日", severity="推荐", target="day",
        condition={"fact": "facts.jishen.tian_de.hit", "op": "eq", "value": True},
        explanation="用事日值天德（本月天德在{facts.jishen.tian_de.target}），按本规则记为正向证据。",
        notes=(
            "待考证：天德能否解三煞/岁破诸凶，各派强度不一（《协纪辨方书》有「虽吉星不能解」之文，"
            "专指岁破），故本规则不进否决层、不抵扣硬伤；"
            "四维卦月（卯/午/酉/子）取支有口径 tiande_guaxiang 两说，报告须回显。"
        ),
        source="《协纪辨方书》", entry="义例·天德", score_weight=1.0,
    ),
    rule(
        "PUB-YUEDE-001", "月德日", severity="推荐", target="day",
        condition={"fact": "facts.jishen.yue_de.hit", "op": "eq", "value": True},
        explanation="用事日干为月德（{facts.jishen.yue_de.gan}），按本规则记为正向证据。",
        notes=(
            "待考证：月德取三合局阳干，起例诸本一致（寅午戌丙、亥卯未甲、申子辰壬、巳酉丑庚），"
            "但「值月德即百事大吉」是断言，本规则只作正向证据、不进否决层。"
        ),
        source="《协纪辨方书》", entry="义例·月德", score_weight=1.0,
    ),
    rule(
        "PUB-YUEDE-HE-001", "月德合日", severity="可用", target="day",
        condition={"fact": "facts.jishen.yue_de.he_hit", "op": "eq", "value": True},
        explanation="用事日干为月德合（{facts.jishen.yue_de.he_gan}），按本规则记为可用参考。",
        notes="待考证：月德合取月德干之五合（丙辛/甲己/丁壬/乙庚），力度弱于月德本干。",
        source="《协纪辨方书》", entry="义例·月德合", score_weight=0.5,
    ),
    rule(
        "PUB-TIANSHE-001", "天赦日", severity="推荐", target="day",
        condition={"fact": "facts.jishen.tian_she.hit", "op": "eq", "value": True},
        explanation="用事日为天赦日（{facts.jishen.tian_she.season}季{facts.jishen.tian_she.day_ganzhi}日），按本规则记为正向证据。",
        notes=(
            "待考证：天赦「百无禁忌」之说流传广而原文待核；四季取支（春戊寅/夏甲午/秋戊申/冬甲子）"
            "诸本一致，是否只在特定事项上成立未定，故不进否决层。"
        ),
        source="《协纪辨方书》", entry="义例·天赦", score_weight=1.0,
    ),
]


def _write_yaml(path: Path, header: str, data: dict) -> None:
    Path(path).write_text(
        header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8",
    )
    assert path.exists(), f"未写出: {path}"
    reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert reloaded["rule_id"] == data["rule_id"], f"{path} 回读失败"


def _case(rule_id: str, kind: str, overrides: dict, note: str) -> dict:
    return {
        "case_id": f"RT-{rule_id}-{kind}",
        "kind": "rule_test",
        "rule_id": rule_id,
        "expected": "hit" if kind == "HIT" else "miss",
        "note": note,
        "overrides": overrides,
    }


def _overrides(rule: dict, hit: bool) -> dict:
    """按规则条件构造最小 overrides（只覆盖被引用的 facts 子树）。

    ``cond["fact"]`` 形如 ``facts.zibai.month.wuhuang_hit_palace``：根命名空间
    已固定为 ``facts``，故只把其后的路径包成嵌套字典 —— 不能再套一层 ``facts``
    （第一版多套了一层，向量因此静默失效、全部 MISS：assert 落在「值仍是基准 False」上）。
    """
    cond = rule["condition"]
    fact = cond["fact"]
    root, *rest = fact.split(".")
    assert root == "facts", f"{rule['rule_id']}: 本生成器只处理 facts.* 条件，得到 {fact}"
    assert rest, f"{rule['rule_id']}: 条件缺少子路径"
    value = cond["value"]
    if cond["op"] == "in":
        # 命中取列表首项；未命中取一个必然不在列表内的哨兵字面量
        chosen = value[0] if hit else "__not_in_list__"
    else:
        chosen = bool(value) if hit else (not value)
    node: dict = chosen
    for key in reversed(rest):
        node = {key: node}
    return {"facts": node}


def main() -> None:
    for spec in RULES_SPEC:
        rid = spec["rule_id"]
        target = RULES / "public" / f"{rid}.yaml"
        _write_yaml(target, HEADER, spec)
        for kind, hit in (("HIT", True), ("MISS", False)):
            case = _case(
                rid, kind, _overrides(spec, hit),
                "规则级测试向量：仅验证 DSL 求值是否符合预期，不构成择日断言。",
            )
            path = CASES / f"RT-{rid}-{kind}.yaml"
            _write_yaml(path, "# 由 tools/gen_rules_phase11.py 生成；overrides 相对金标准基准 ctx 深合并。\n", case)
        print(f"✅ {rid}: 规则 + 2 向量")


if __name__ == "__main__":
    main()
