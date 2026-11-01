"""规则库与规则测试向量生成器（一次性工具，产物入库）。

为什么用脚本生成
----------------
41 条规则的公共字段（api_version / version / status / citation 空值 / tests 命名）必须完全一致，
手写极易漂移。本脚本保证：

1. 全部规则 ``status: 待考证``，``citation.quote`` 一律为 ``null``（不编造原文）；
2. 每条规则至少 1 个 hit + 1 个 miss/unknown 的规则级测试向量；
3. 规则 id / 文件路径 / 用例 id 三者一一对应。

**运行后必须人工复核**（Agent 不得自行把 status 改为"已考证"）。
用法：``python3 tools/gen_rules.py``
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "core-rule" / "rules"
CASES = ROOT / "tests" / "cases" / "rule_tests"

HEADER = (
    "# 本文件由 tools/gen_rules.py 生成，结构统一；规则内容（条件/解释/出处）需人类考证者复核。\n"
    "# status: 待考证 = 口诀常见但原文未核，默认不参与正式判定，命中时仅登记为 unknown。\n"
    "# citation.quote 为 null 表示「尚未核对原文」，不是缺漏，禁止为填满字段而编造引文。\n"
)

BUILD_TASKS = ["动土", "修造", "上梁", "竖柱", "安门", "安灶", "入宅", "安葬", "破土", "立碑", "修坟", "修祠", "安龛", "升座"]
ALL_TASKS: list[str] = []  # 空 = 不限事项

SANSHA = "《协纪辨方书》"
TONGSU = "《象吉通书》"
AOTOU = "《鳌头通书》"
YANGGONG = "《杨公忌日》"


def cite(source: str, kind: str = "classic", clause: str | None = None) -> dict:
    return {
        "kind": kind,
        "source": source,
        "edition": None,
        "juan": None,
        "pian": None,
        "entry": None,
        "quote_kind": "原文" if clause else None,
        "quote": clause,
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
    hard_veto: bool,
    target: str,
    condition: dict,
    explanation: str,
    notes: str,
    source: str,
    spec_clause: str | None = None,
    school: str = "public",
    task_kinds: list[str] | None = None,
    node_kinds: list[str] | None = None,
    strictness_min: str = "normal",
    score_weight: float | None = None,
) -> dict:
    return {
        "api_version": 1,
        "rule_id": rule_id,
        "version": 1,
        "school": school,
        "category": category,
        # 定义级 = 干支算术推论（有 spec_clause），其余为断言级待考证
        "status": "定义级" if spec_clause else "待考证",
        "hard_veto": hard_veto,
        "severity": severity,
        "target": target,
        "applies_to": {
            "task_kinds": task_kinds if task_kinds is not None else ALL_TASKS,
            "node_kinds": node_kinds or [],
            "strictness_min": strictness_min,
        },
        "condition": condition,
        "score_weight": score_weight,
        "citation": cite(source, kind="spec" if spec_clause else "classic", clause=spec_clause),
        "tests": [],  # 由 main() 回填
        "explanation": explanation,
        "supersedes": None,
        "notes": notes,
    }


def fact(path: str, op: str, value=None, value_from: str | None = None) -> dict:
    node: dict = {"fact": path, "op": op}
    if value_from is not None:
        node["value_from"] = value_from
    elif value is not None:
        node["value"] = value
    return node


def sg(a: str, b: str, kind: str) -> dict:
    return {"fact": a, "op": "same_group", "value": {"path": b, "kind": kind}}


RULES_SPEC: list[dict] = [
    # ================= 年煞 =================
    rule("PUB-TAISUI-001", "太岁占山", severity="禁用", hard_veto=True, target="mountain",
         condition=fact("facts.taisui.zhi", "eq", value_from="site.shan_jia_zhi"),
         explanation="坐山山家为{site.shan_jia_zhi}，与本年年支太岁所临之方相同，按本规则判为禁用。",
         notes="待考证：太岁占位宽度（一山或一支）、是否以立春换年、兼向是否同论。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    rule("PUB-SUIPO-001", "岁破占山", severity="禁用", hard_veto=True, target="mountain",
         condition=fact("facts.suipo.hit_mountain", "eq", True),
         explanation="坐山{site.mountain}落于岁破之方（太岁对冲），按本规则判为禁用。",
         notes="待考证：岁破与三煞重叠时的优先级；是否仅忌坐山不忌向首。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    rule("PUB-SANSHA-001", "三煞占山（年）", severity="禁用", hard_veto=True, target="mountain",
         condition=fact("facts.sansha.year.hit_mountain", "eq", True),
         explanation="坐山{site.mountain}落于年支三合局所临三煞之方，按本规则判为禁用。",
         notes="待考证：三煞是否按年/月/日/时四层分别起煞；三山与劫/灾/岁的对应；兼向是否同论。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    rule("PUB-SANSHA-002", "三煞占山（月）", severity="禁用", hard_veto=True, target="mountain",
         condition=fact("facts.sansha.month.hit_mountain", "eq", True),
         explanation="坐山{site.mountain}落于月支三合局所临三煞之方，按本规则判为禁用。",
         notes="待考证：月三煞是否与年三煞同权；月建以节气换月还是农历月换月。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    rule("PUB-SANSHA-003", "三煞占向", severity="禁用", hard_veto=True, target="facing",
         condition=fact("facts.sansha.year.hit_facing", "eq", True),
         explanation="向首{site.facing}落于年支三合局所临三煞之方，按本规则判为禁用。",
         notes="待考证：三煞是否忌向（部分流派只论坐山）。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    rule("PUB-WUHUANG-001", "五黄占山", severity="禁用", hard_veto=True, target="mountain",
         condition=fact("facts.wuhuang.year.hit_mountain", "eq", True),
         explanation="坐山{site.mountain}落于年五黄所临之方，按本规则判为禁用。",
         notes="待考证：入中基准年、顺飞/逆飞、是否随年支切换、是否忌向。",
         source=AOTOU, task_kinds=BUILD_TASKS),
    # ================= 月煞 =================
    rule("PUB-YUEPO-001", "月破占山", severity="禁用", hard_veto=True, target="mountain",
         condition=fact("facts.yuepo.hit_mountain", "eq", True),
         explanation="坐山{site.mountain}与本月月建相冲（月破），按本规则判为禁用。",
         notes="待考证：月破与月建占山是否互斥；月建口径随 CalendarConfig。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    rule("PUB-YUEJIAN-001", "月建占山", severity="慎用", hard_veto=False, target="mountain",
         condition=fact("site.shan_jia_zhi", "eq", value_from="time.month_zhi"),
         explanation="坐山山家{site.shan_jia_zhi}与本月月建{time.month_zhi}同支，按本规则判为慎用。",
         notes="待考证：月建占山是否成立、是否仅忌动土修造。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    # ================= 日时 =================
    rule("PUB-CHONGSHAN-001", "日冲山", severity="禁用", hard_veto=True, target="day",
         condition=sg("site.shan_jia_zhi", "course.day.zhi", "chong"),
         explanation="日支{course.day.zhi}与坐山山家{site.shan_jia_zhi}相冲，按本规则判为禁用。",
         notes="待考证：四维山无地支时如何取山家；兼向取何山。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    rule("PUB-CHONGSHAN-002", "时冲山", severity="慎用", hard_veto=False, target="hour",
         condition=sg("site.shan_jia_zhi", "course.hour.zhi", "chong"),
         explanation="时支{course.hour.zhi}与坐山山家{site.shan_jia_zhi}相冲，按本规则判为慎用。",
         notes="待考证：时冲山是否成立、是否仅在 strict 下生效。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    rule("PUB-CHONGMING-001", "日冲命", severity="禁用", hard_veto=True, target="person",
         condition=sg("person.year_zhi", "course.day.zhi", "chong"),
         explanation="日支{course.day.zhi}与命主年命{person.year_zhi}相冲，按本规则判为禁用。",
         notes="待考证：以年命支还是年命纳音为准；多命主时是否逐一检查。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    rule("PUB-CHONGMING-002", "时冲命", severity="慎用", hard_veto=False, target="person",
         condition=sg("person.year_zhi", "course.hour.zhi", "chong"),
         explanation="时支{course.hour.zhi}与命主年命{person.year_zhi}相冲，按本规则判为慎用。",
         notes="待考证：时冲命是否与日冲命同权。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    rule("PUB-SILI-001", "四离日", severity="禁用", hard_veto=True, target="day",
         condition=fact("facts.sili_sijue.has_sili", "eq", True),
         explanation="用事日为四离日（二分二至前一日），按本规则判为禁用。",
         notes="待考证：取前一日还是当日；是否只忌出行、不忌修造。",
         source=SANSHA),
    rule("PUB-SIJUE-001", "四绝日", severity="禁用", hard_veto=True, target="day",
         condition=fact("facts.sili_sijue.has_sijue", "eq", True),
         explanation="用事日为四绝日（四立前一日），按本规则判为禁用。",
         notes="待考证：取前一日还是当日；是否只忌出行。",
         source=SANSHA),
    rule("PUB-YANGGONG-001", "杨公忌日", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.yangongji.value", "exists"),
         explanation="用事日可能为杨公忌日，但本系统未内置该表，需人工复核。",
         notes="有争议：杨公忌日列表存在多种版本（13 日/29 日说），本系统不提供该事实。",
         source=YANGGONG),
    # ================= 结构检测 =================
    rule("PUB-SANHEFU-001", "三合扶山", severity="推荐", hard_veto=False, target="mountain",
         condition=fact("facts.structure.sanhe_with_mountain", "count_gte", 1),
         explanation="日课地支与山家{site.shan_jia_zhi}构成三合局，按本规则记为正向结构证据。",
         notes="正向证据不等于可用结论：仍须通过否决层。是否需局生山家，待考证。",
         source=SANSHA, task_kinds=BUILD_TASKS, score_weight=1.0),
    rule("PUB-BANHE-001", "半合扶山", severity="可用", hard_veto=False, target="mountain",
         condition=fact("facts.structure.banhe_with_mountain", "count_gte", 1),
         explanation="日课地支与山家{site.shan_jia_zhi}构成半合，按本规则记为参考。",
         notes="半合力度弱于三合，仅作参考；生地/墓地半合之别待考证。",
         source=SANSHA, task_kinds=BUILD_TASKS, score_weight=0.5),
    # ================= 方位（本系统不提供，规则须 unknown） =================
    rule("PUB-YINFU-001", "阴府", severity="慎用", hard_veto=False, target="mountain",
         condition=fact("facts.yinfu.candidates.value", "exists"),
         explanation="阴府须以坐山纳音与日课天干化气生克取，本系统未裁定取用体系，需人工复核。",
         notes="有争议：单干亦忌 vs 须双干成煞；坐山纳音取用体系（分金/穿山）未裁定。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    rule("PUB-DUTIAN-001", "都天煞", severity="慎用", hard_veto=False, target="mountain",
         condition=fact("facts.dutiansha.value", "exists"),
         explanation="都天煞本系统未内置推算表，需人工复核。",
         notes="待考证：都天煞起例存在多版本。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    rule("PUB-FUBING-001", "伏兵大祸", severity="慎用", hard_veto=False, target="mountain",
         condition=fact("facts.fubing_dahuo.value", "exists"),
         explanation="伏兵大祸本系统未内置推算表，需人工复核。",
         notes="待考证：伏兵大祸起例与年干/山家关系。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    rule("PUB-GUANGFU-001", "天地官符", severity="慎用", hard_veto=False, target="mountain",
         condition=fact("facts.tianguan_difu.value", "exists"),
         explanation="天地官符本系统未内置推算表，需人工复核。",
         notes="待考证：天地官符起例。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    rule("PUB-DAXIAOYUE-001", "大小月建", severity="慎用", hard_veto=False, target="mountain",
         condition=fact("facts.damonthly_jian.value", "exists"),
         explanation="大小月建本系统未内置推算表，需人工复核。",
         notes="待考证：大小月建起例。",
         source=TONGSU, task_kinds=BUILD_TASKS),
    # ================= 事项专属 =================
    rule("PUB-SANG-001", "重丧日（安葬专属）", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.sang.value", "exists"),
         explanation="重丧日本系统未内置推算表，安葬用事须人工复核。",
         notes="待考证：重丧日推算表与是否只忌安葬。",
         source=TONGSU, task_kinds=["安葬", "破土", "立碑", "修坟"]),
    rule("PUB-SANG-002", "三丧日（安葬专属）", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.sang.value", "exists"),
         explanation="三丧日本系统未内置推算表，安葬用事须人工复核。",
         notes="待考证：三丧日推算表。",
         source=TONGSU, task_kinds=["安葬", "破土", "立碑", "修坟"]),
    rule("PUB-JIAQU-001", "妨翁姑（嫁娶专属）", severity="慎用", hard_veto=False, target="person",
         condition=fact("facts.jiaqu.value", "exists"),
         explanation="妨翁姑本系统未内置推算表，嫁娶用事须人工复核。",
         notes="待考证：妨翁姑的推算依据与是否仍适用。",
         source=TONGSU, task_kinds=["嫁娶", "纳采"]),
    rule("PUB-JIAQU-002", "妨父母（嫁娶专属）", severity="慎用", hard_veto=False, target="person",
         condition=fact("facts.jiaqu.value", "exists"),
         explanation="妨父母本系统未内置推算表，嫁娶用事须人工复核。",
         notes="待考证：妨父母的推算依据。",
         source=TONGSU, task_kinds=["嫁娶", "纳采"]),
    rule("PUB-XIUJIU-001", "修旧宅加严项", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.xiujiu.value", "exists"),
         explanation="修旧宅/宗祠在 strict 档下须额外核查加严项，本系统未内置该表。",
         notes="待考证：修旧宅加严项清单。",
         source=TONGSU, task_kinds=["修祠", "修坟", "修造"], strictness_min="strict"),
    # ================= 相主 =================
    rule("PUB-MING-SANSHA-001", "年命三煞", severity="禁用", hard_veto=True, target="person",
         condition=sg("person.year_zhi", "facts.sansha.year.mountains.0", "sanhe"),
         explanation="命主年命与三煞所临之方同属一局，按本规则判为禁用。",
         notes="待考证：年命三煞是否以命主年支三合局取、是否只忌坐山。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    rule("PUB-XIANGSHOU-001", "相主（日干与年命）", severity="慎用", hard_veto=False, target="person",
         condition={"all": [fact("person.year_zhi", "exists"),
                            fact("facts.structure.gan_chong_pairs", "count_gte", 1)]},
         explanation="日课天干与命主关系需人工复核（本规则仅作提示）。",
         notes="待考证：命主五行与日干关系的判定口径（纳音还是正五行）。",
         source=TONGSU),
    # ================= 正五行派（默认关闭） =================
    rule("ZWX-FUSHAN-001", "扶山（正五行）", school="zhengwuxing", severity="推荐", hard_veto=False,
         target="mountain",
         condition=fact("facts.structure.sanhe_with_mountain", "count_gte", 1),
         explanation="日课与山家构成三合局，正五行视角记为扶山正向证据。",
         notes="待考证：是否须局五行生山家五行、补龙与扶山是否同论。",
         source=SANSHA, task_kinds=BUILD_TASKS, score_weight=1.0),
    rule("ZWX-BULONG-001", "补龙（正五行）", school="zhengwuxing", severity="可用", hard_veto=False,
         target="day",
         condition=fact("facts.structure.sanhe_groups", "count_gte", 1),
         explanation="日课地支成三合局，正五行视角记为补龙参考。",
         notes="待考证：补龙须先定龙脉五行，本系统未采集该输入，故仅作参考。",
         source=SANSHA, task_kinds=["安葬", "修坟", "修祠"]),
    rule("ZWX-XIANGSHOU-001", "相主（正五行）", school="zhengwuxing", severity="可用", hard_veto=False,
         target="person",
         condition=fact("person.year_zhi", "exists"),
         explanation="命主年命已录入，正五行相主判定需人类裁定口径后启用。",
         notes="待考证：相主以年命纳音还是年支五行。",
         source=SANSHA, task_kinds=BUILD_TASKS),
    # ================= 斗首 / 玄空（默认关闭，仅参考层） =================
    rule("DS-HUAQI-001", "斗首化气", school="doushou", severity="可用", hard_veto=False, target="day",
         condition=fact("facts.structure.gan_he_pairs", "count_gte", 1),
         explanation="日课天干见五合，斗首视角记为化气参考（不参与否决）。",
         notes="待考证：斗首化气起例、是否参与否决。默认 participates_in_veto=false。",
         source=AOTOU),
    rule("XK-GUAQI-001", "玄空卦气", school="xuankong", severity="可用", hard_veto=False,
         target="mountain",
         condition=fact("facts.wuhuang.year.palace", "exists"),
         explanation="玄空卦气需运星与山向星配合，本系统仅提供年五黄宫位作参考。",
         notes="待考证：玄空大卦卦气起例、是否参与否决。默认只进参考层。",
         source=AOTOU),
]

# --------------------------------------------------------------------------- #
# 定义级规则（status: 定义级，citation.kind: spec）
#
# 判定标准（ADR-0007）：该规则只描述"干支系统的算术推论"（关系识别、计数、归属），
# 不含"吉/凶/宜/忌"断言。出处是内核规格条款，不是古籍原文。
#
# 严重度说明：冲突类结构给"慎用"（影响 tier，依据 2026-11-01 评审裁定：
# 结构性冲突按 MEDIUM_AVOID 处理）；合类结构给"可用"（中性，仅展示，不拉高也不拉低）。

# --------------------------------------------------------------------------- #
# 定义级规则（status: 定义级，citation.kind: spec）
#
# 判定标准（ADR-0007）：该规则只描述"干支系统的算术推论"（关系识别、计数、归属），
# 不含"吉/凶/宜/忌"断言。出处是内核规格条款，不是古籍原文。
#
# 严重度说明：冲突类结构给"慎用"（影响 tier，依据 2026-11-01 评审裁定：
# 结构性冲突按 MEDIUM_AVOID 处理）；合类结构给"可用"（中性，仅展示，不拉高也不拉低）。
# --------------------------------------------------------------------------- #
DEFINITIONAL_SPEC: list[dict] = [
    rule("DEF-ZIXING-001", "自刑结构", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.zixing_pairs", "count_gte", 1),
         explanation="四柱地支出现自刑（辰辰/午午/酉酉/亥亥），该结构确定成立。",
         notes="severity=记录：只陈述结构事实，不表达吉凶。是否「见之即忌」属断言，见 ASSERT-ZIXING-001。",
         source="core-symbol spec §3.2 自刑表",
         spec_clause="自刑四组：辰辰、午午、酉酉、亥亥。未未不在其列，只能按地支重复处理。"),
    rule("DEF-CHONG-001", "日时相冲结构", severity="记录", hard_veto=False, target="day",
         condition=sg("course.day.zhi", "course.hour.zhi", "chong"),
         explanation="日支{course.day.zhi}与时支{course.hour.zhi}构成六冲，该结构确定成立。",
         notes="severity=记录：只陈述冲的事实。是否「冲即忌」属断言，见 ASSERT-CHONG-001。",
         source="core-symbol spec §3.1 六冲表",
         spec_clause="六冲：子午、丑未、寅申、卯酉、辰戌、巳亥。"),
    rule("DEF-XING-001", "三刑结构", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.xing_pairs", "count_gte", 1),
         explanation="四柱地支构成三刑（寅巳申/丑戌未/子卯），该结构确定成立。",
         notes="severity=记录：自刑单列于 DEF-ZIXING-001。是否「刑即为凶」属断言，见 ASSERT-XING-001。",
         source="core-symbol spec §3.1 三刑表",
         spec_clause="三刑：寅巳申、丑戌未、子卯。自刑（辰午酉亥）单列。"),
    rule("DEF-HAI-001", "六害结构", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.hai_pairs", "count_gte", 1),
         explanation="四柱地支构成六害，该结构确定成立。",
         notes="severity=记录：只陈述害的事实。是否「害即为凶」属断言，见 ASSERT-HAI-001。",
         source="core-symbol spec §3.1 六害表",
         spec_clause="六害：子未、丑午、寅巳、卯辰、申亥、酉戌。"),
    rule("DEF-PO-001", "相破结构", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.po_pairs", "count_gte", 1),
         explanation="四柱地支构成相破，该结构确定成立。",
         notes="severity=记录：只陈述破的事实。是否「破即为凶」属断言，见 ASSERT-PO-001。",
         source="core-symbol spec §3.1 相破表",
         spec_clause="相破：子酉、丑辰、寅亥、卯午、巳申、未戌。"),
    rule("DEF-REPEAT-001", "地支重复结构", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.max_repeat", "gte", 3),
         explanation="四柱地支出现三见以上重复（最多{facts.structure.max_repeat}见），该结构确定成立。",
         notes="severity=记录：只陈述重复次数。是否「三见为滞」属断言，见 ASSERT-REPEAT-001；伏吟是否成立由流派规则解释。",
         source="core-symbol spec §3.3 重复计数",
         spec_clause="max_repeat = 四柱地支中同一支出现次数的最大值。重复是计数事实，不预设吉凶。"),
    rule("DEF-XUNKONG-001", "旬空结构", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.xunkong.hits", "count_gte", 1),
         explanation="四柱地支落入日柱所在旬的空亡，该结构确定成立。",
         notes="severity=记录：只陈述旬空事实。是否「空即忌」属断言，见 ASSERT-XUNKONG-001。",
         source="core-symbol spec §3.4 旬空表",
         spec_clause="甲子旬空戌亥、甲戌旬空申酉、甲申旬空午未、甲午旬空辰巳、甲辰旬空寅卯、甲寅旬空子丑。"),
    rule("DEF-GANCHONG-001", "天干相冲结构", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.gan_chong_pairs", "count_gte", 1),
         explanation="四柱天干构成相冲（甲庚/乙辛/丙壬/丁癸），该结构确定成立。",
         notes="severity=记录：只陈述天干冲的事实。是否「冲即为凶」属断言，见 ASSERT-GANCHONG-001。",
         source="core-symbol spec §3.1 天干相冲表",
         spec_clause="天干相冲：甲庚、乙辛、丙壬、丁癸（阳对阳、阴对阴，隔四相冲）。"),
    rule("DEF-SANHE-001", "三合局成立", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.sanhe_groups", "count_gte", 1),
         explanation="四柱地支构成完整三合局，该结构确定成立（三支齐现）。",
         notes="severity=记录：中性结构事实。是否「三合即吉」属断言，见 PUB-SANHEFU-001（待考证）。",
         source="core-symbol spec §3.1 三合表",
         spec_clause="三合局：申子辰水、亥卯未木、寅午戌火、巳酉丑金；需三支齐现方成立。"),
    rule("DEF-SANHE-MOUNTAIN-001", "山家三合结构", severity="记录", hard_veto=False, target="mountain",
         condition=fact("facts.structure.sanhe_with_mountain", "count_gte", 1),
         explanation="坐山山家{site.shan_jia_zhi}与日课地支构成完整三合局，该结构确定成立。",
         notes="severity=记录：中性结构事实。是否「扶山为吉」属断言，见 PUB-SANHEFU-001（待考证）。",
         source="core-symbol spec §3.5 山家三合",
         spec_clause="山家三合：坐山（含兼山）地支与日课地支构成完整三合局（三支齐现）。"),
]

# --------------------------------------------------------------------------- #
# 断言级规则（status: 待考证，severity 为吉凶值）
#
# 与 DEFINITIONAL_SPEC 一一对应：定义级只说"结构是什么"，本组才说"好不好"。
# 分离的理由（ADR-0009）：把 severity=慎用 挂在定义级规则上，等于用"已确定"的
# 外衣包装未考证的吉凶判断 —— 这是本体系最容易被腐蚀的地方。
#
# 所有断言级规则的 citation.quote 均为 null，等待人类考证者补原文。
# --------------------------------------------------------------------------- #
ASSERTION_SPEC: list[dict] = [
    rule("ASSERT-ZIXING-001", "自刑为凶", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.zixing_pairs", "count_gte", 1),
         explanation="四柱地支见自刑（辰辰/午午/酉酉/亥亥），按本规则判为慎用。",
         notes="断言级：自刑是否主凶、是否只忌特定用事，需原文确认。结构事实见 DEF-ZIXING-001。",
         source=SANSHA),
    rule("ASSERT-CHONG-001", "日时相冲为凶", severity="记录", hard_veto=False, target="day",
         condition=sg("course.day.zhi", "course.hour.zhi", "chong"),
         explanation="日支{course.day.zhi}与时支{course.hour.zhi}相冲，按本规则判为慎用。",
         notes="断言级：日时相冲是否成立、是否只忌时级用事，需原文确认。结构事实见 DEF-CHONG-001。",
         source=TONGSU),
    rule("ASSERT-XING-001", "三刑为凶", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.xing_pairs", "count_gte", 1),
         explanation="四柱地支构成三刑，按本规则判为慎用。",
         notes="断言级：三刑是否须三支齐现、子卯相刑是否同论，需原文确认。结构事实见 DEF-XING-001。",
         source=SANSHA),
    rule("ASSERT-HAI-001", "六害为凶", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.hai_pairs", "count_gte", 1),
         explanation="四柱地支构成六害，按本规则判为慎用。",
         notes="断言级：六害在择日中是否成立，需原文确认。结构事实见 DEF-HAI-001。",
         source=TONGSU),
    rule("ASSERT-PO-001", "相破为凶", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.po_pairs", "count_gte", 1),
         explanation="四柱地支构成相破，按本规则判为慎用。",
         notes="断言级：相破是否成立、是否只作提示，需原文确认。结构事实见 DEF-PO-001。",
         source=TONGSU),
    rule("ASSERT-REPEAT-001", "三见为滞", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.max_repeat", "gte", 3),
         explanation="四柱地支出现三见以上重复（最多{facts.structure.max_repeat}见），按本规则判为慎用。",
         notes=(
             "断言级：'三见主滞、用事宜慎'是吉凶主张，不是计数定义。"
             "计数事实见 DEF-REPEAT-001（severity=记录）。"
             "本条即 2026-11-01 评审要求从 DEF-REPEAT-001 拆出的断言部分。"
         ),
         source=TONGSU),
    rule("ASSERT-XUNKONG-001", "旬空为凶", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.xunkong.hits", "count_gte", 1),
         explanation="四柱地支落入日柱所在旬的空亡，按本规则判为慎用。",
         notes="断言级：空亡是否忌用事、以日柱还是时柱起旬，需原文确认。结构事实见 DEF-XUNKONG-001。",
         source=TONGSU),
    rule("ASSERT-GANCHONG-001", "天干相冲为凶", severity="记录", hard_veto=False, target="day",
         condition=fact("facts.structure.gan_chong_pairs", "count_gte", 1),
         explanation="四柱天干构成相冲（甲庚/乙辛/丙壬/丁癸），按本规则判为慎用。",
         notes="断言级：天干相冲在择日中是否成立，需原文确认。结构事实见 DEF-GANCHONG-001。",
         source=TONGSU),
]

# --------------------------------------------------------------------------- #
# 断言级规则（status: 待考证，severity 为吉凶值）
#
# 与 DEFINITIONAL_SPEC 一一对应：定义级只说"结构是什么"，本组才说"好不好"。
# 分离的理由（ADR-0009）：把 severity=慎用 挂在定义级规则上，等于用"已确定"的
# 外衣包装未考证的吉凶判断 —— 这是本体系最容易被腐蚀的地方。
#
# 所有断言级规则的 citation.quote 均为 null，等待人类考证者补原文。
# --------------------------------------------------------------------------- #
ASSERTION_SPEC: list[dict] = [
    rule("ASSERT-ZIXING-001", "自刑为凶", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.structure.zixing_pairs", "count_gte", 1),
         explanation="四柱地支见自刑（辰辰/午午/酉酉/亥亥），按本规则判为慎用。",
         notes="断言级：自刑是否主凶、是否只忌特定用事，需原文确认。结构事实见 DEF-ZIXING-001。",
         source=SANSHA),
    rule("ASSERT-CHONG-001", "日时相冲为凶", severity="慎用", hard_veto=False, target="day",
         condition=sg("course.day.zhi", "course.hour.zhi", "chong"),
         explanation="日支{course.day.zhi}与时支{course.hour.zhi}相冲，按本规则判为慎用。",
         notes="断言级：日时相冲是否成立、是否只忌时级用事，需原文确认。结构事实见 DEF-CHONG-001。",
         source=TONGSU),
    rule("ASSERT-XING-001", "三刑为凶", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.structure.xing_pairs", "count_gte", 1),
         explanation="四柱地支构成三刑，按本规则判为慎用。",
         notes="断言级：三刑是否须三支齐现、子卯相刑是否同论，需原文确认。结构事实见 DEF-XING-001。",
         source=SANSHA),
    rule("ASSERT-HAI-001", "六害为凶", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.structure.hai_pairs", "count_gte", 1),
         explanation="四柱地支构成六害，按本规则判为慎用。",
         notes="断言级：六害在择日中是否成立，需原文确认。结构事实见 DEF-HAI-001。",
         source=TONGSU),
    rule("ASSERT-PO-001", "相破为凶", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.structure.po_pairs", "count_gte", 1),
         explanation="四柱地支构成相破，按本规则判为慎用。",
         notes="断言级：相破是否成立、是否只作提示，需原文确认。结构事实见 DEF-PO-001。",
         source=TONGSU),
    rule("ASSERT-REPEAT-001", "三见为滞", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.structure.max_repeat", "gte", 3),
         explanation="四柱地支出现三见以上重复（最多{facts.structure.max_repeat}见），按本规则判为慎用。",
         notes=(
             "断言级：'三见主滞、用事宜慎'是吉凶主张，不是计数定义。"
             "计数事实见 DEF-REPEAT-001（severity=记录）。"
             "本条即 2026-11-01 评审要求从 DEF-REPEAT-001 拆出的断言部分。"
         ),
         source=TONGSU),
    rule("ASSERT-XUNKONG-001", "旬空为凶", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.xunkong.hits", "count_gte", 1),
         explanation="四柱地支落入日柱所在旬的空亡，按本规则判为慎用。",
         notes="断言级：空亡是否忌用事、以日柱还是时柱起旬，需原文确认。结构事实见 DEF-XUNKONG-001。",
         source=TONGSU),
    rule("ASSERT-GANCHONG-001", "天干相冲为凶", severity="慎用", hard_veto=False, target="day",
         condition=fact("facts.structure.gan_chong_pairs", "count_gte", 1),
         explanation="四柱天干构成相冲（甲庚/乙辛/丙壬/丁癸），按本规则判为慎用。",
         notes="断言级：天干相冲在择日中是否成立，需原文确认。结构事实见 DEF-GANCHONG-001。",
         source=TONGSU),
]

RULES_SPEC.extend(DEFINITIONAL_SPEC)
RULES_SPEC.extend(ASSERTION_SPEC)

# --------------------------------------------------------------------------- #
# 规则级测试向量：rule_id → (hit_overrides, miss_overrides)
# miss_overrides 为 None 表示"该规则在当前事实下只能 unknown"，生成 unknown 用例。
# 基准 ctx = 金标准案例（2027-07-11 未时，乾山巽向兼亥巳，修祠），见 tests/conftest.py
# --------------------------------------------------------------------------- #
VECTORS: dict[str, tuple] = {
    "PUB-TAISUI-001": ({"site": {"shan_jia_zhi": "未"}}, {}),
    "PUB-SUIPO-001": ({"facts": {"suipo": {"hit_mountain": True}}}, {}),
    "PUB-SANSHA-001": ({"facts": {"sansha": {"year": {"hit_mountain": True}}}}, {}),
    "PUB-SANSHA-002": ({"facts": {"sansha": {"month": {"hit_mountain": True}}}}, {}),
    "PUB-SANSHA-003": ({"facts": {"sansha": {"year": {"hit_facing": True}}}}, {}),
    "PUB-WUHUANG-001": ({"facts": {"wuhuang": {"year": {"hit_mountain": True}}}}, {}),
    "PUB-YUEPO-001": ({"facts": {"yuepo": {"hit_mountain": True}}}, {}),
    "PUB-YUEJIAN-001": ({"site": {"shan_jia_zhi": "未"}, "time": {"month_zhi": "未"}}, {}),
    "PUB-CHONGSHAN-001": ({"course": {"day": {"zhi": "巳"}}}, {}),
    "PUB-CHONGSHAN-002": ({"course": {"hour": {"zhi": "巳"}}}, {}),
    "PUB-CHONGMING-001": ({"person": {"year_zhi": "酉"}}, {"person": {"year_zhi": "丑"}}),
    "PUB-CHONGMING-002": ({"person": {"year_zhi": "丑"}}, {"person": {"year_zhi": "子"}}),
    "PUB-SILI-001": ({"facts": {"sili_sijue": {"has_sili": True}}}, {}),
    "PUB-SIJUE-001": ({"facts": {"sili_sijue": {"has_sijue": True}}}, {}),
    "PUB-YANGGONG-001": ({"facts": {"yangongji": {"value": {"table": "待人工录入"}}}}, None),
    "DEF-ZIXING-001": ({"facts": {"structure": {"zixing_pairs": [{"a": "辰", "b": "辰"}]}}}, {}),
    "DEF-CHONG-001": ({"course": {"hour": {"zhi": "酉"}}}, {}),
    "DEF-XING-001": ({"facts": {"structure": {"xing_pairs": [{"a": "寅", "b": "巳"}]}}}, {}),
    "DEF-HAI-001": ({"facts": {"structure": {"hai_pairs": [{"a": "子", "b": "未"}]}}}, {}),
    "DEF-PO-001": ({"facts": {"structure": {"po_pairs": [{"a": "子", "b": "酉"}]}}}, {}),
    "DEF-REPEAT-001": ({"facts": {"structure": {"max_repeat": 3}}},
                       {"facts": {"structure": {"max_repeat": 2}}}),
    "DEF-XUNKONG-001": ({"facts": {"xunkong": {"hits": ["戌"]}}}, {"facts": {"xunkong": {"hits": []}}}),
    "DEF-GANCHONG-001": ({"facts": {"structure": {"gan_chong_pairs": [{"a": "甲", "b": "庚"}]}}},
                        {"facts": {"structure": {"gan_chong_pairs": []}}}),
    "PUB-SANHEFU-001": ({}, {"facts": {"structure": {"sanhe_with_mountain": []}}}),
    "PUB-BANHE-001": ({}, {"facts": {"structure": {"banhe_with_mountain": []}}}),
    "PUB-YINFU-001": ({"facts": {"yinfu": {"candidates": {"value": {"hits": ["丁"]}}}}}, None),
    "PUB-DUTIAN-001": ({"facts": {"dutiansha": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-FUBING-001": ({"facts": {"fubing_dahuo": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-GUANGFU-001": ({"facts": {"tianguan_difu": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-DAXIAOYUE-001": ({"facts": {"damonthly_jian": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-SANG-001": ({"facts": {"sang": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-SANG-002": ({"facts": {"sang": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-JIAQU-001": ({"facts": {"jiaqu": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-JIAQU-002": ({"facts": {"jiaqu": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-XIUJIU-001": ({"facts": {"xiujiu": {"value": {"table": "待人工录入"}}}}, None),
    "PUB-MING-SANSHA-001": ({"person": {"year_zhi": "子"}}, {"person": {"year_zhi": "丑"}}),
    "PUB-XIANGSHOU-001": (
        {"person": {"year_zhi": "丑"}, "facts": {"structure": {"gan_chong_pairs": [{"a": "丁", "b": "癸"}]}}},
        {"person": {"year_zhi": "丑"}, "facts": {"structure": {"gan_chong_pairs": []}}},
    ),
    "ZWX-FUSHAN-001": ({}, {"facts": {"structure": {"sanhe_with_mountain": []}}}),
    "ZWX-BULONG-001": ({"facts": {"structure": {"sanhe_groups": [{"group": ["亥", "卯", "未"], "element": "木"}]}}},
                       {"facts": {"structure": {"sanhe_groups": []}}}),
    "DEF-SANHE-001": (
        {"facts": {"structure": {"sanhe_groups": [{"group": ["亥", "卯", "未"], "element": "木"}]}}},
        {"facts": {"structure": {"sanhe_groups": []}}},
    ),
    "DEF-SANHE-MOUNTAIN-001": ({}, {"facts": {"structure": {"sanhe_with_mountain": []}}}),
    "DEF-SANHE-001": (
        {"facts": {"structure": {"sanhe_groups": [{"group": ["亥", "卯", "未"], "element": "木"}]}}},
        {"facts": {"structure": {"sanhe_groups": []}}},
    ),
    "DEF-SANHE-MOUNTAIN-001": ({}, {"facts": {"structure": {"sanhe_with_mountain": []}}}),
    "ASSERT-ZIXING-001": ({"facts": {"structure": {"zixing_pairs": [{"a": "辰", "b": "辰"}]}}}, {}),
    "ASSERT-CHONG-001": ({"course": {"hour": {"zhi": "酉"}}}, {}),
    "ASSERT-XING-001": ({"facts": {"structure": {"xing_pairs": [{"a": "寅", "b": "巳"}]}}}, {}),
    "ASSERT-HAI-001": ({"facts": {"structure": {"hai_pairs": [{"a": "子", "b": "未"}]}}}, {}),
    "ASSERT-PO-001": ({"facts": {"structure": {"po_pairs": [{"a": "子", "b": "酉"}]}}}, {}),
    "ASSERT-REPEAT-001": ({"facts": {"structure": {"max_repeat": 3}}},
                          {"facts": {"structure": {"max_repeat": 2}}}),
    "ASSERT-XUNKONG-001": ({"facts": {"xunkong": {"hits": ["戌"]}}},
                           {"facts": {"xunkong": {"hits": []}}}),
    "ASSERT-GANCHONG-001": ({"facts": {"structure": {"gan_chong_pairs": [{"a": "甲", "b": "庚"}]}}},
                            {"facts": {"structure": {"gan_chong_pairs": []}}}),
    "ASSERT-ZIXING-001": ({"facts": {"structure": {"zixing_pairs": [{"a": "辰", "b": "辰"}]}}}, {}),
    "ASSERT-CHONG-001": ({"course": {"hour": {"zhi": "酉"}}}, {}),
    "ASSERT-XING-001": ({"facts": {"structure": {"xing_pairs": [{"a": "寅", "b": "巳"}]}}}, {}),
    "ASSERT-HAI-001": ({"facts": {"structure": {"hai_pairs": [{"a": "子", "b": "未"}]}}}, {}),
    "ASSERT-PO-001": ({"facts": {"structure": {"po_pairs": [{"a": "子", "b": "酉"}]}}}, {}),
    "ASSERT-REPEAT-001": ({"facts": {"structure": {"max_repeat": 3}}},
                          {"facts": {"structure": {"max_repeat": 2}}}),
    "ASSERT-XUNKONG-001": ({"facts": {"xunkong": {"hits": ["戌"]}}},
                           {"facts": {"xunkong": {"hits": []}}}),
    "ASSERT-GANCHONG-001": ({"facts": {"structure": {"gan_chong_pairs": [{"a": "甲", "b": "庚"}]}}},
                            {"facts": {"structure": {"gan_chong_pairs": []}}}),
    "ZWX-XIANGSHOU-001": ({"person": {"year_zhi": "丑"}}, None),
    "DS-HUAQI-001": ({"facts": {"structure": {"gan_he_pairs": [{"a": "丁", "b": "壬"}]}}}, {}),
    "XK-GUAQI-001": ({}, {"facts": {"wuhuang": {"year": {"palace": None}}}}, "unknown"),
}


def write_rule(spec: dict) -> Path:
    school = spec["school"]
    out_dir = RULES / school
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec['rule_id']}.yaml"
    body = yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, default_flow_style=False, width=120)
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def write_case(rule_id: str, expected: str, overrides: dict) -> str:
    case_id = f"RT-{rule_id}-{expected.upper()}"
    case = {
        "case_id": case_id,
        "kind": "rule_test",
        "rule_id": rule_id,
        "expected": expected,
        "note": "规则级测试向量：仅验证 DSL 求值是否符合预期，不构成择日断言。",
        "overrides": overrides,
    }
    path = CASES / f"{case_id}.yaml"
    path.write_text(
        "# 由 tools/gen_rules.py 生成；overrides 相对金标准基准 ctx 深合并。\n"
        + yaml.safe_dump(case, allow_unicode=True, sort_keys=False, default_flow_style=False, width=120),
        encoding="utf-8",
    )
    return case_id


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    for stale in CASES.glob('*.yaml'):
        stale.unlink()
    # 清理已从 RULES_SPEC 移除的旧规则文件，避免"文档说 44 条、磁盘上 52 条"的漂移
    keep = {spec["rule_id"] for spec in RULES_SPEC}
    for old in RULES.rglob("*.yaml"):
        if old.stem not in keep:
            old.unlink()
    # 清理已从 RULES_SPEC 移除的旧规则文件，避免"文档说 44 条、磁盘上 52 条"的漂移
    keep = {spec["rule_id"] for spec in RULES_SPEC}
    for old in RULES.rglob("*.yaml"):
        if old.stem not in keep:
            old.unlink()
    for stale in CASES.glob('*.yaml'):
        stale.unlink()
    missing = [s["rule_id"] for s in RULES_SPEC if s["rule_id"] not in VECTORS]
    if missing:
        raise SystemExit(f"以下规则缺少测试向量: {missing}")
    total_cases = 0
    for spec in RULES_SPEC:
        rule_id = spec["rule_id"]
        vector = VECTORS[rule_id]
        hit_ov, miss_ov = vector[0], vector[1]
        miss_expected = vector[2] if len(vector) > 2 else "miss"
        tests = [write_case(rule_id, "hit", hit_ov)]
        if miss_ov is None:
            tests.append(write_case(rule_id, "unknown", {}))
        else:
            tests.append(write_case(rule_id, miss_expected, miss_ov))
        spec["tests"] = tests
        write_rule(spec)
        total_cases += len(tests)
    print(f"rules: {len(RULES_SPEC)}  cases: {total_cases}")


if __name__ == "__main__":
    main()
