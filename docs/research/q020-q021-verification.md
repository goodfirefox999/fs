# 宣称核对（tools/verify_claims.py 可复跑输出）

| 宣称 | 实际路径 | 用例名 | 结果 |
|---|---|---|---|
| Q-020 三煞范围已上锁（TestSanshaScope，含「壬山不算三煞」） （该文件共 38 例全部通过=True） | `tests/unit/test_paipan_fixed.py` | `tests.unit.test_paipan_fixed.TestSanshaScope::test_year_sansha_is_hai_zi_chou_for_wu_year`<br>`tests.unit.test_paipan_fixed.TestSanshaScope::test_three_mountains_hit`<br>`tests.unit.test_paipan_fixed.TestSanshaScope::test_ren_mountain_is_not_sansha_hit`<br>`tests.unit.test_paipan_fixed.TestSanshaScope::test_sansha_has_no_palace_field` | ✅ 属实 |
| Q-021 兼向已解耦为数值口径（jianxiang.yaml + TestJianxiangCaliber） （threshold_deg=True, 口径数=2） | `core-rule/config/calibers/jianxiang.yaml` | `tests.unit.test_paipan_fixed.TestJianxiangCaliber::test_default_threshold_is_3_0`<br>`tests.unit.test_paipan_fixed.TestJianxiangCaliber::test_default_caliber_marks_jian`<br>`tests.unit.test_paipan_fixed.TestJianxiangCaliber::test_alternative_caliber_marks_zhengzhen`<br>`tests.unit.test_paipan_fixed.TestJianxiangCaliber::test_caliber_is_echoed_in_manifest`<br>`tests.unit.test_paipan_fixed.TestJianxiangCaliber::test_unknown_caliber_rejected` | ✅ 属实 |

## 附录：BRE `\|` 陷阱演示（toybox grep，可复跑）

- grep 实现：`toybox 0.8.13 (is not GNU grep 9.0)`
- BRE `A\|B`：命中 0 个文件（**静默零匹配 = 假阴性**）
- `-E 'A|B'`：命中 1 个文件（正确）

**纪律：交替模式必须 `grep -E "A|B"` 或 Python 遍历；`\|` 在 toybox/BSD grep 下静默零匹配。**