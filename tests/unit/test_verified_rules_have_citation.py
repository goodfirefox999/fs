"""已考证规则必须有完整引文；首批影印引文不得被改写或"提升"。

核对基准（2026-11-03）：浙江大学图书馆藏《欽定四庫全書·子部七·術數類》
《協紀辨方書》卷五影印本，Internet Archive item ``06056506.cn``；
三合六合条另据卷六影印本，item ``06056507.cn``。
各规则的 ``quote`` 均按影印逐字录入；因缺人类签名，``status`` 仍为「待考证」。
"""

from __future__ import annotations

import pytest

from core_eval.engine import UNKNOWN_UNVERIFIED, classify_unknown
from core_rule import default_registry

#: 四条首批考证规则：rule_id → 影印原文（逐字，含异体字，禁止改写为简体通行本）。
SCAN_QUOTES = {
    "PUB-TIANDE-001": (
        "乾坤寶典曰天德者天之福德也所理之方所值之日可以興土功營宮室"
        "○堪輿經曰天德者正月丁二月坤三月壬四月辛五月乾六月甲七月癸八月艮"
        "九月丙十月乙十一月巽十二月庚"
    ),
    "PUB-YUEDE-001": (
        "天寶曆曰月德者月之德神也取土修營宜向其方宴樂上官利用其日"
        "○曆例曰月德者正五九月在丙二六十月在甲三七十一月在壬四八十二月在庚"
    ),
    "PUB-YUEDE-HE-001": (
        "五行論曰月德合者五行之精符會為合也所理之地衆惡皆消所值之日百福並集"
        "利以出師命將上冊受封祠祀星辰營建宮室"
        "○曆例曰月德合者正五九月在辛二六十月在己三七十一月在丁四八十二月在乙"
        "○考原曰月德合者即各以月德所合之干為之"
    ),
    "PUB-TIANSHE-001": (
        "天寶曆曰天赦者赦過宥罪之辰也天之生育甲與戊地之成立子午寅申"
        "故以甲戊配成天赦其日可以緩刑獄雪寃枉施恩惠若與德神會合尤宜興造"
        "○曆例曰春戊寅夏甲午秋戊申冬甲子是也"
    ),
}

IA_ITEM = "https://archive.org/details/06056506.cn"

#: 卷六首批：评分层（三合派）六合规则，条件已按原文改为「月建六合日」。
LIUHE_RULE = "SH-LIUHE-001"
LIUHE_QUOTE = (
    "神樞經曰六合者日月合宿之辰也其日宜會賓客結婚姻立契券合交易"
    "○李鼎祚曰正月在亥逆行十二辰○考原曰六合者月建與月將相合也"
)
IA_VOL6 = "https://archive.org/details/06056507.cn"

#: 所有已按影印填写 quote 的规则（含仍为待考证者）。
FILLED_RULES = set(SCAN_QUOTES) | {LIUHE_RULE}


@pytest.fixture(scope="module")
def registry():
    return default_registry()


def _verified_rules(registry):
    return [r for r in registry.ruleset.rules if r.status == "已考证"]


def test_every_verified_rule_has_complete_citation(registry):
    """status=已考证 必须能落到影印：原文 + 卷/篇 + 签名 + 可复查路径。"""
    problems: list[str] = []
    for rule in _verified_rules(registry):
        c = rule.citation
        missing = []
        if c.kind != "classic":
            missing.append("kind≠classic")
        if not c.source:
            missing.append("source 空")
        if not c.has_quote:
            missing.append("quote 空")
        if c.quote_kind != "原文":
            missing.append(f"quote_kind={c.quote_kind!r}")
        if not c.verified_by:
            missing.append("verified_by 空（须人类签名）")
        if not (c.pian or c.juan):
            missing.append("pian/juan 均空")
        if not c.url_or_path:
            missing.append("url_or_path 空（A 级证据须可复查）")
        if missing:
            problems.append(f"{rule.rule_id}: " + "、".join(missing))
    assert not problems, "已考证规则引文不完整：\n" + "\n".join(problems)


@pytest.mark.parametrize("rule_id", sorted(SCAN_QUOTES))
def test_scan_quotes_match_the_printed_page(registry, rule_id):
    """四条规则必须与影印逐字一致；改成通行本/白话转述即失败。"""
    rule = registry.ruleset.by_id[rule_id]
    c = rule.citation
    assert c.quote == SCAN_QUOTES[rule_id], (
        f"{rule_id} 的 quote 与 2026-11-03 影印核对结果不符——"
        "改写引文等同于伪造出处"
    )
    assert c.quote_kind == "原文"
    assert c.juan == "五"
    assert c.edition and "06056506.cn" in c.edition
    assert c.url_or_path.startswith(IA_ITEM)
    assert c.confidence == "高"
    assert c.book_authenticity == "authentic"


@pytest.mark.parametrize(
    ("rule_id", "wrong", "right"),
    [
        ("PUB-YUEDE-HE-001", "二六十月在巳", "二六十月在己"),
    ],
)
def test_yuede_he_dingzi_follows_the_scan(registry, rule_id, wrong, right):
    """定字以影印为准：维基文库四库本作「巳」，影印本作「己」。

    同一叶「戊在巳為金母」的「巳」是闭合方框，此处是开口形，与同版
    《天德合》「六月己」字形一致；且月德合取月德之五合（甲己合），
    故从影印作「己」。这条测试防止有人按在线文本「顺手改正」回去。
    """
    quote = registry.ruleset.by_id[rule_id].citation.quote
    assert right in quote
    assert wrong not in quote


def test_liuhe_quote_matches_the_printed_page(registry):
    """六合条按卷六影印逐字录入；卷次误标为「卷二·本原」等旧值即失败。"""
    c = registry.ruleset.by_id[LIUHE_RULE].citation
    assert c.quote == LIUHE_QUOTE
    assert c.quote_kind == "原文"
    assert c.juan == "六"
    assert c.pian == "义例四·六合"
    assert c.edition and "06056507.cn" in c.edition
    assert c.url_or_path.startswith(IA_VOL6)
    assert c.confidence == "高"
    assert c.book_authenticity == "authentic"


def test_filled_quotes_do_not_let_unverified_rules_vote(registry):
    """补了 quote 也不等于已考证：待考证规则默认仍不得进入判定。"""
    voting = {r.rule_id for r in registry.ruleset.select(include_unverified=False)}
    assert not (FILLED_RULES & voting), "待考证规则不得因填了 quote 而参与投票"

    all_rules = {r.rule_id for r in registry.ruleset.select(include_unverified=True)}
    assert FILLED_RULES <= all_rules, "include_unverified=True 时应能取到这些规则"


def test_promotion_is_gated_by_human_signature(registry):
    """已补原文的规则目前均未签名；一旦提升为「已考证」，必须同时留下签名与日期。"""
    for rule_id in FILLED_RULES:
        rule = registry.ruleset.by_id[rule_id]
        if rule.status == "已考证":
            assert rule.citation.verified_by, f"{rule_id} 已考证却无 verified_by"
            assert rule.citation.verified_at, f"{rule_id} 已考证却无 verified_at"


def test_unverified_remedy_separates_missing_quote_from_missing_signature(registry):
    """已补原文的待考证规则只缺签名；补救文案不得再让人「去补原文」或叠书名号。"""
    filled = registry.ruleset.by_id["PUB-TIANDE-001"]
    reason, remedy = classify_unknown(filled, participation="仅登记", unknown_paths=())
    assert reason == UNKNOWN_UNVERIFIED
    assert "签名" in remedy and "需补" not in remedy
    assert "《《" not in remedy

    empty = registry.ruleset.by_id["PUB-SUIPO-001"]
    reason, remedy = classify_unknown(empty, participation="仅登记", unknown_paths=())
    assert reason == UNKNOWN_UNVERIFIED
    assert "原文" in remedy
    assert "《《" not in remedy and "》》" not in remedy
