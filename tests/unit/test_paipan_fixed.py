"""排盘固定规则回归测试：建除 / 黄黑道 / 五黄换年 / 四废季节。

为什么单独成文件：这四项都属于「死规则」层——起例固定、结果唯一、无派别辩解空间。
它们出错的方式也很一致：**不是算错，是取错了输入**（换年点、季节界、命中粒度）。
因此每条都配一个「按旧口径会算错」的具体日期，防止回归。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from core_symbol import (
    GANZHI60,
    HEI_DAO_STARS,
    HUANG_DAO_STARS,
    HUANGDAO_STARS,
    JIANCHU_STARS,
    MOUNTAINS_24,
    ZHI,
    Mountain,
    huangdao_index,
    huangdao_of,
    jianchu_index,
    jianchu_of,
    mountain_by_name,
    wuhuang_year,
    wuhuang_year_of_date,
)
from core_symbol.huangdao import QINGLONG_START_ZHI
from core_symbol.zibai import year_center_star

ROOT = Path(__file__).resolve().parents[2]
TZ = ZoneInfo("Asia/Shanghai")


# --------------------------------------------------------------------------- #
# 建除十二神
# --------------------------------------------------------------------------- #
class TestJianchu:
    def test_star_order_is_canonical(self) -> None:
        assert JIANCHU_STARS == ("建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭")

    def test_jian_day_is_the_month_branch_day(self) -> None:
        """恒等式一：月建之日即为「建」。"""
        for month_zhi in ZHI:
            assert jianchu_of(month_zhi, month_zhi) == "建"
            assert jianchu_index(month_zhi, month_zhi) == 0

    def test_po_day_is_the_chong_of_month_branch(self) -> None:
        """恒等式二：建除之「破」必然就是月破日（日支冲月建）。

        这条把建除与「月破」两套独立起例锁在一起：任一方表错即在此暴露。
        """
        for month_zhi in ZHI:
            po_zhi = ZHI[(ZHI.index(month_zhi) + 6) % 12]
            assert jianchu_of(month_zhi, po_zhi) == "破", (month_zhi, po_zhi)

    def test_all_twelve_stars_reachable_in_order(self) -> None:
        """月建起顺数十二月，应逐一取到十二建星（不跳、不重）。"""
        for month_zhi in ZHI:
            got = [jianchu_of(month_zhi, ZHI[(ZHI.index(month_zhi) + k) % 12]) for k in range(12)]
            assert tuple(got) == JIANCHU_STARS

    def test_known_course_2027_07_11(self) -> None:
        """2027-07-11：未月卯日 → 未建、申除、酉满、戌平、亥定、子执、丑破、寅危、卯成。"""
        assert jianchu_of("未", "卯") == "成"

    def test_illegal_zhi_rejected(self) -> None:
        with pytest.raises(ValueError):
            jianchu_of("未", "X")


# --------------------------------------------------------------------------- #
# 十二黄黑道（青龙十二神）
# --------------------------------------------------------------------------- #
class TestHuangdao:
    def test_star_order_is_canonical(self) -> None:
        assert HUANGDAO_STARS == (
            "青龙", "明堂", "天刑", "朱雀", "金匮", "天德",
            "白虎", "玉堂", "天牢", "玄武", "司命", "勾陈",
        )

    def test_dao_grouping_partitions_twelve_stars(self) -> None:
        """黄道六神 + 黑道六神 = 十二神，且互不相交（分组是参考表，不入事实层）。"""
        assert len(HUANG_DAO_STARS) == 6
        assert len(HEI_DAO_STARS) == 6
        assert HUANG_DAO_STARS.isdisjoint(HEI_DAO_STARS)
        assert set(HUANGDAO_STARS) == HUANG_DAO_STARS | HEI_DAO_STARS

    def test_qinglong_start_table_covers_twelve_months(self) -> None:
        assert set(QINGLONG_START_ZHI) == set(ZHI)
        # 口诀「子午临申地，丑未戌上行，寅申须加子，卯酉却居寅，辰戌龙位上，巳亥午中寻」
        assert QINGLONG_START_ZHI["子"] == QINGLONG_START_ZHI["午"] == "申"
        assert QINGLONG_START_ZHI["丑"] == QINGLONG_START_ZHI["未"] == "戌"
        assert QINGLONG_START_ZHI["寅"] == QINGLONG_START_ZHI["申"] == "子"
        assert QINGLONG_START_ZHI["卯"] == QINGLONG_START_ZHI["酉"] == "寅"
        assert QINGLONG_START_ZHI["辰"] == QINGLONG_START_ZHI["戌"] == "辰"
        assert QINGLONG_START_ZHI["巳"] == QINGLONG_START_ZHI["亥"] == "午"

    def test_month_branch_day_is_qinglong(self) -> None:
        for month_zhi in ZHI:
            assert huangdao_of(month_zhi, QINGLONG_START_ZHI[month_zhi]) == "青龙"

    def test_gouchen_cross_validation(self) -> None:
        """交叉校验（非自证）：与既有勾陈黑道表逐月吻合 12/12。

        ``donggong_gouchen_heidao.json`` 是独立录入的「勾陈日」表（按月建查日支），
        勾陈是十二神的第 12 位，故本模块起例顺行 11 位后必须逐月命中同一日支。
        两者若有一处不合，说明青龙起例或顺行方向至少有一处错了。
        """
        data = json.loads(
            (ROOT / "core-rule" / "config" / "data" / "donggong_gouchen_heidao.json").read_text(
                encoding="utf-8"
            )
        )
        by_month = data["by_month_branch"]
        assert set(by_month) == set(ZHI), "勾陈表应覆盖十二月建"
        for month_zhi, day_zhis in by_month.items():
            for day_zhi in day_zhis:
                assert huangdao_of(month_zhi, day_zhi) == "勾陈", (month_zhi, day_zhi)
                assert huangdao_index(month_zhi, day_zhi) == 11

    def test_hour_star_uses_same_formula(self) -> None:
        """时家黄黑道与日家同一公式：月建之时的青龙位由时支决定。"""
        assert huangdao_of("未", "戌") == "青龙"
        # 未月（青龙起戌）未时：戌→子序差 9 位 → 玄武
        assert huangdao_of("未", "未") == "玄武"

    def test_known_course_2027_07_11(self) -> None:
        """2027-07-11 未月卯日：戌青龙 → 卯为第六位（天德，黄道）。"""
        assert huangdao_of("未", "卯") == "天德"

    def test_illegal_month_rejected(self) -> None:
        with pytest.raises(ValueError):
            huangdao_of("X", "子")


# --------------------------------------------------------------------------- #
# 五黄换年点（紫白年 = 立春换年）
# --------------------------------------------------------------------------- #
class TestWuhuangYearBoundary:
    def test_zibai_year_before_lichun_uses_previous_year(self) -> None:
        """2027-01-15 尚未立春，紫白年仍是 2026：一白入中、五黄在离（正南）。

        旧实现按公历年取 2027 → 九紫入中、五黄在坎（正北），
        与同一张盘上的 facts.zibai.year 恰好相差两位五、方位相反。
        """
        wh = wuhuang_year_of_date(date(2027, 1, 15), "午")  # 年支仍属丙午（2026）
        assert wh.value["zibai_year"] == 2026
        assert wh.value["center_star"] == year_center_star(2026) == 1
        assert wh.value["palace"] == "离"

    def test_after_lichun_stays_current_year(self) -> None:
        wh = wuhuang_year_of_date(date(2027, 7, 11), "未")  # 丁未年
        assert wh.value["zibai_year"] == 2027
        assert wh.value["center_star"] == 9
        assert wh.value["palace"] == "坎"

    def test_matches_zibai_year_plate_consistency(self) -> None:
        """年五黄与年紫白必须同源：五黄所临宫 == 由入中星顺飞四步所得宫。"""
        from core_symbol.zibai import FLY_ORDER

        for y in range(2024, 2030):
            wh = wuhuang_year(y)
            center = year_center_star(y)
            expected_palace = FLY_ORDER[(5 - center) % 9][0]
            assert wh.value["palace"] == expected_palace
            assert wh.value["center_star"] == center

    def test_palace_level_hit_covers_eight_stem_mountains(self) -> None:
        """2024 年五黄在兑宫：庚/酉/辛三山同受。

        旧字段 ``hit_mountain`` 只认宫心那一山（酉），庚山、辛山会漏判——
        这是「宫级神煞按山名精确匹配」的典型错法。
        """
        wh = wuhuang_year(2024)
        assert wh.value["palace"] == "兑"
        assert wh.value["mountain"] == "酉"  # 山级：仅宫心那一山
        assert set(wh.value["palace_mountains"]) == {"庚", "酉", "辛"}  # 宫级：一宫三山

    def test_palace_mountains_partition_all_24(self) -> None:
        """八宫 × 三山 = 二十四山，无重无漏（中宫无山，不列）。"""
        from core_symbol.zibai import PALACE_MOUNTAINS

        assert set(PALACE_MOUNTAINS) == {"坎", "艮", "震", "巽", "离", "坤", "兑", "乾"}
        flat: list[str] = []
        for palace, mountains in PALACE_MOUNTAINS.items():
            assert len(mountains) == 3, palace
            flat.extend(mountains)
        assert sorted(flat) == sorted(MOUNTAINS_24), "宫→山映射必须恰好覆盖二十四山各一次"


# --------------------------------------------------------------------------- #
# 四废季节：按节气月，不按公历月
# --------------------------------------------------------------------------- #
class TestSifeiSeason:
    """四废口诀「春庚申辛酉、夏壬子癸亥、秋甲寅乙卯、冬丙午丁巳」，四季以四立为界。"""

    @staticmethod
    def _facts(d: date) -> dict:
        from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
        from core_time import CalendarConfig

        return build_context(
            course=CourseSpec(dt=datetime(d.year, d.month, d.day, 10, 0, tzinfo=TZ)),
            site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            cal=CalendarConfig(),
        )["facts"]

    def test_spring_starts_at_lichun_not_march(self) -> None:
        """2027-02-10 庚申日：已过立春（2/4）属春 → 四废命中。

        按公历月取季（2 月归冬）会查冬表（丙午/丁巳），此日漏判。
        """
        f = self._facts(date(2027, 2, 10))
        assert f["_calibers"]  # 上下文可用
        assert f["donggong"]["is_dasha"] is True

    def test_winter_starts_at_lidong_not_december(self) -> None:
        """2027-11-23 丙午日：已过立冬（11/7）属冬 → 四废命中。

        按公历月取季（11 月归秋）会查秋表（甲寅/乙卯），此日漏判。
        """
        f = self._facts(date(2027, 11, 23))
        assert f["donggong"]["is_dasha"] is True

    def test_non_sifei_day_not_flagged(self) -> None:
        """反证：同一季节里非四废日不得命中（避免「整季都判四废」的假阳性）。"""
        f = self._facts(date(2027, 7, 11))  # 辛卯日，夏（未月），非壬子/癸亥
        assert f["donggong"]["is_dasha"] is False

    def test_season_mapping_is_by_month_branch(self) -> None:
        from core_symbol.registry import _season_of_month_zhi

        assert _season_of_month_zhi("寅") == _season_of_month_zhi("卯") == _season_of_month_zhi("辰") == "spring"
        assert _season_of_month_zhi("巳") == _season_of_month_zhi("午") == _season_of_month_zhi("未") == "summer"
        assert _season_of_month_zhi("申") == _season_of_month_zhi("酉") == _season_of_month_zhi("戌") == "autumn"
        assert _season_of_month_zhi("亥") == _season_of_month_zhi("子") == _season_of_month_zhi("丑") == "winter"
        with pytest.raises(ValueError):
            _season_of_month_zhi("X")


# --------------------------------------------------------------------------- #
# 三煞作用范围：锁定「壬山不命中」（QUESTION Q-020）
# --------------------------------------------------------------------------- #
class TestSanshaScope:
    """三煞只按三山判，**不得**被"好心"改成宫级（Q-020）。

    为什么要上锁：2026 丙午年三煞在亥子丑。亥(322.5–337.5)、子(352.5–7.5)、
    丑(22.5–37.5) 之间留了 337.5–352.5 的空档，恰好是壬山。按八宫并集补壬，
    会连带扩到乾、艮共 9 山——那是把「三山」偷换成「整方」，不是修 bug。
    """

    @staticmethod
    def _facts(d: date, azimuth: float) -> dict:
        from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
        from core_time import CalendarConfig

        return build_context(
            course=CourseSpec(dt=datetime(d.year, d.month, d.day, 10, 0, tzinfo=TZ)),
            site=SiteSpec(azimuth_deg=azimuth, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            cal=CalendarConfig(),
        )

    def test_year_sansha_is_hai_zi_chou_for_wu_year(self) -> None:
        """2026 丙午年（寅午戌火局）→ 三煞在亥子丑（北方）。"""
        facts = self._facts(date(2026, 7, 1), 0.0)["facts"]
        assert facts["sansha"]["year"]["mountains"] == ["亥", "子", "丑"]

    def test_three_mountains_hit(self) -> None:
        """亥(330°)、子(0°)、丑(30°) 三山必须命中——这是三煞的正面。"""
        for azimuth in (330.0, 0.0, 30.0):
            ctx = self._facts(date(2026, 7, 1), azimuth)
            mountain = ctx["site"]["mountain"]
            assert ctx["facts"]["sansha"]["year"]["hit_mountain"] is True, mountain

    def test_ren_mountain_is_not_sansha_hit(self) -> None:
        """壬山(345°)落在亥与子之间的空档，**不命中**。

        这条断言是"锁"：若有人为了"补漏"把命中改成宫级，此测试立刻变红，
        并把人引到 Q-020 的概念争议上，而不是让人以为自己在修 bug。
        """
        ctx = self._facts(date(2026, 7, 1), 345.0)
        assert ctx["site"]["mountain"] == "壬"
        assert ctx["facts"]["sansha"]["year"]["hit_mountain"] is False
        # 反证：壬山确实落在「煞北大方向」里，所以这个 False 不是"判错了方位"，
        # 而是"三煞按三山判"的口径结果。
        assert ctx["facts"]["sansha"]["year"]["direction"] == "北"

    def test_sansha_has_no_palace_field(self) -> None:
        """三煞事实**不得**出现 hit_palace：五黄可以按宫，三煞不行（Q-020）。"""
        facts = self._facts(date(2026, 7, 1), 0.0)["facts"]
        for basis in ("year", "month"):
            assert "hit_palace" not in facts["sansha"][basis]
            assert "palace_mountains" not in facts["sansha"][basis]


# --------------------------------------------------------------------------- #
# 兼向阈值：数值口径（QUESTION Q-021）
# --------------------------------------------------------------------------- #
class TestJianxiangCaliber:
    """阈值是**口径**不是常量：两说并存，改 config 换口径，不改代码。

    偏 3.5° 的坐向正好落在两说的分歧区：默认（正针 6°/兼 4.5°）判兼，
    另一说（正针 9°/兼 3°）判正针。这条测试同时证明 config 真的被读到了。
    """

    AZIMUTH_IN_DISPUTE = 318.5  # 乾山山心 315° + 3.5°

    @staticmethod
    def _ctx(selection: dict[str, str] | None) -> dict:
        from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
        from core_rule.calibers import load_caliber_sets
        from core_time import CalendarConfig

        calibers = load_caliber_sets()
        if selection:
            calibers = calibers.with_selection(selection)
        return build_context(
            course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=TZ)),
            site=SiteSpec(azimuth_deg=TestJianxiangCaliber.AZIMUTH_IN_DISPUTE, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            cal=CalendarConfig(),
            calibers=calibers,
        )

    def test_default_threshold_is_3_0(self) -> None:
        """默认口径 zheng6_jian45 = 3.0°，与历史行为一致（不得无声漂移）。"""
        from core_rule.calibers import CALIBER_JIANXIANG, load_caliber_sets

        reg = load_caliber_sets()
        assert reg.chosen(CALIBER_JIANXIANG) == "zheng6_jian45"
        assert reg.params(CALIBER_JIANXIANG)["threshold_deg"] == 3.0

    def test_default_caliber_marks_jian(self) -> None:
        ctx = self._ctx(None)
        assert ctx["site"]["jian"] == "亥"
        assert ctx["site"]["shan_jia_zhi"] == "亥"
        assert ctx["site"]["jian_threshold_deg"] == 3.0

    def test_alternative_caliber_marks_zhengzhen(self) -> None:
        """切到 zheng9_jian3（4.5°）后，同一坐向改判正针，且山家地支随之变 None。"""
        ctx = self._ctx({"jianxiang": "zheng9_jian3"})
        assert ctx["site"]["jian"] is None
        assert ctx["site"]["shan_jia_zhi"] is None
        assert ctx["site"]["jian_threshold_deg"] == 4.5
        assert ctx["site"]["jian_caliber"] == "zheng9_jian3"

    def test_caliber_is_echoed_in_manifest(self) -> None:
        """口径必须在 manifest 回显，否则报告无法回答"这次用了哪一说"。"""
        ctx = self._ctx({"jianxiang": "zheng9_jian3"})
        manifest = ctx["_meta"]["calibers"]
        assert "jianxiang" in manifest["sets"]
        assert manifest["selection"]["jianxiang"] == "zheng9_jian3"

    def test_unknown_caliber_rejected(self) -> None:
        from core_rule.errors import DSLValidationError
        from core_rule.calibers import load_caliber_sets

        with pytest.raises(DSLValidationError):
            load_caliber_sets().with_selection({"jianxiang": "no_such_caliber"})


# --------------------------------------------------------------------------- #
# 集成：新事实进入 ctx 且时家与日家分开
# --------------------------------------------------------------------------- #
class TestFactsIntegration:
    @staticmethod
    def _ctx(d: date, hour: int) -> dict:
        from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
        from core_time import CalendarConfig

        return build_context(
            course=CourseSpec(dt=datetime(d.year, d.month, d.day, hour, 0, tzinfo=TZ)),
            site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            cal=CalendarConfig(),
        )

    def test_jianchu_and_huangdao_present_with_hour(self) -> None:
        facts = self._ctx(date(2027, 7, 11), 14)["facts"]
        assert facts["jianchu"]["star"] == "成"
        assert facts["jianchu"]["hour"]["star"] == "建"  # 未时 == 月建
        assert facts["huangdao"]["day"]["star"] == "天德"
        assert facts["huangdao"]["hour"]["star"] == "玄武"

    def test_hour_facts_differ_across_hours_same_day(self) -> None:
        """时家建除/黄黑道必须逐时重算（日级缓存不得把首个子时的值串给其余时辰）。"""
        sub = self._ctx(date(2027, 7, 11), 0)["facts"]  # 子时
        wu = self._ctx(date(2027, 7, 11), 12)["facts"]  # 午时
        assert sub["jianchu"]["hour"]["star"] != wu["jianchu"]["hour"]["star"]
        assert sub["huangdao"]["hour"]["star"] != wu["huangdao"]["hour"]["star"]

    def test_wuhuang_year_matches_zibai_year_plate(self) -> None:
        """同一盘上「年五黄」与「年紫白」不得互相矛盾（曾经一个报北、一个报南）。"""
        for d in (date(2027, 1, 15), date(2027, 2, 10), date(2027, 7, 11), date(2027, 12, 20)):
            facts = self._ctx(d, 10)["facts"]
            zibai_center = facts["zibai"]["year"]["center"]
            assert facts["wuhuang"]["year"]["center_star"] == zibai_center
            assert facts["wuhuang"]["year"]["zibai_year"] == facts["zibai"]["year"]["zibai_year"]

    def test_mountain_exports_jian_xiang(self) -> None:
        """兼向判定必须可被外部导入（曾在 __all__ 缺项，只对内可见）。"""
        from core_symbol.mountain import jian_xiang

        assert jian_xiang(mountain_by_name("子")) is None  # 山心 → 正针
        m = mountain_by_name("乾")  # 乾山山心 315°
        at_35 = Mountain(index=m.index, name=m.name, center_deg=m.center_deg, azimuth=318.5)
        assert jian_xiang(at_35) == "亥", "偏移 3.5° 超默认阈值 3° → 兼亥"
        # 阈值取 4.5°（9°/3°/3° 说的正针带半宽）时，同一盘改判正针：
        # 这正是「兼向阈值」两说会影响山家地支、进而影响三合扶山的地方。
        assert jian_xiang(at_35, threshold_deg=4.5) is None
        assert jian_xiang(mountain_by_name("乾"), threshold_deg=4.5) is None


def test_every_registered_fact_root_is_materialized() -> None:
    """登记 ≠ 落地：FACT_REGISTRY 里每条事实的根命名空间必须真的出现在 facts 里。

    这条守护针对「注册表写了、derive_facts 没实现」的假账（历史上 zibai 曾整块死代码）。
    """
    from datetime import datetime

    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
    from core_symbol import FACT_REGISTRY
    from core_time import CalendarConfig

    facts = build_context(
        course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=TZ)),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )["facts"]
    missing = sorted({spec.name.split(".")[0] for spec in FACT_REGISTRY} - set(facts))
    assert missing == [], f"以下事实已登记但未落地到 facts：{missing}"


def test_ganzhi60_reference_is_stable() -> None:
    """跑一遍常量表，防止顺带改动导致六十甲子错位（其他测试都依赖它）。"""
    assert GANZHI60[0] == "甲子"
    assert GANZHI60[59] == "癸亥"
    assert len(GANZHI60) == 60
