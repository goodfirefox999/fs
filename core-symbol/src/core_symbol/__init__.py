"""core-symbol：择日引擎符号层。

提供干支属性、干支关系、纳音、旬空、二十四山、分金与派生事实（神煞方位）。

**禁止**在本层出现吉凶宜忌（架构铁律 3）。关系是"是什么"，不是"好不好"。
"""

from __future__ import annotations

from .ganzhi import (
    GAN,
    GANZHI60,
    GAN_CHONG,
    GAN_HE,
    GAN_WUXING,
    GAN_YINYANG,
    LIUCHONG,
    LIUHAI,
    LIUHE,
    PO,
    SANHE,
    SANHUI,
    SANXING,
    WUXING,
    ZHI,
    ZHI_WUXING,
    ZHI_YINYANG,
    ZIXING,
    ZhiRelation,
    all_relations_between_zhi,
    relation_between_gan,
    relation_between_zhi,
    same_group,
    sanhe_group_of,
    sanhe_present,
    sanhui_present,
    wuxing_of_gan,
    wuxing_of_zhi,
    zhi_counts,
    zhi_relations_in,
)
from .huangdao import (
    HEI_DAO_STARS,
    HUANGDAO_STARS,
    HUANG_DAO_STARS,
    QINGLONG_START_ZHI,
    huangdao_index,
    huangdao_of,
)
from .jianchu import JIANCHU_STARS, jianchu_index, jianchu_of
from .mountain import (
    MOUNTAINS_24,
    FenJin,
    Mountain,
    angular_distance,
    facing_of,
    fenjin_of_azimuth,
    jian_xiang,
    mountain_by_name,
    mountain_of_azimuth,
    normalize_azimuth,
)
from .nayin import (
    NAYIN_TABLE,
    XUNKONG_TABLE,
    XunKong,
    nayin_element_of,
    nayin_of,
    xun_head_of,
    xunkong_hit,
    xunkong_of,
)
from .registry import FACT_REGISTRY, FactSpec, derive_facts, fact_status_summary, unavailable_facts
from .shensha import (
    FactStatus,
    FactValue,
    mountain_hits_azimuth,
    sansha_of,
    sili_sijue,
    suipo_azimuth,
    taisui_azimuth,
    unverified_fact,
    wuhuang_month,
    wuhuang_year,
    wuhuang_year_of_date,
    yinfu_candidates,
    yuepo_azimuth,
    zhi_of_azimuth,
)

__all__ = [name for name in dir() if not name.startswith("_")]

__version__ = "0.1.0"
