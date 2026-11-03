# grep/工具行为证据审计（tools/audit_grep_findings.py 输出）

| ID | 出处 | 结论 | 复核 | 三态 |
|---|---|---|---|---|
| C-01 | 评审四·片1 重写：TestRepoIsClean 已剥离 | 片1（8f2217f）不含仓库级断言，单独检出可绿 | git show 8f2217f + Python find（非 grep 判定） | ✅ 成立 |
| C-02 | 取证 §6.6 / q020-q021-verification.md | Q-020 TestSanshaScope 存在且全过 | Python 遍历（verify_claims.py 同源） | ✅ 成立 |
| C-03 | 取证 §6.6 / q020-q021-verification.md | Q-021 jianxiang.yaml 两口径 + TestJianxiangCaliber | yaml 解析：calibers=2 | ✅ 成立 |
| C-04 | 取证 §6.6 根因修正 | engine.py 无 NUL、合法 UTF-8（「判二进制」误诊不成立） | NUL=False, utf8=True | ✅ 成立 |
| C-05 | test_no_total_rank / CHANGELOG | _total_rank/_mean_rank_score 已从 engine/ranker 语法树消失 | AST 复扫干净 | ✅ 成立 |
| C-06 | CHANGELOG / rules lint 输出 | 规则库 86 条（manifest 计数） | loader 计数=86 | ✅ 成立 |
| C-07 | 2026-11-03 上午汇报 | 旧链未上远端：origin/main == 64f5be5 | 64f5be5 补 spec §6 字面仲裁金测试：三煞 reject + 正五行 favorable + 董公直星不能覆盖 | ✅ 成立 |
| C-08 | 2026-11-03 上午汇报 | pytest 汇总行不可见 → **边界修正**：仅 -q 下消失，非 -q 正常 | -q 汇总消失=True，非 -q 可见=True | ✅ 成立 |
| | ↳ 备注：此前 CHANGELOG/记忆写的是绝对表述，需改为「-q 下」 | | | |
| C-09 | 并发取证（mtime 表） | huangdao/jianchu 等文件由并行会话写入 | mtime 是一次性快照证据；维持结论但标注：不可机器复跑，如需复核须重新取样 | ⚠️ 证据不足 |
| C-10 | 2026-11-03 上午汇报 | stash@{0} 的 base 在新链可达，重写未破坏 stash | eac493d 是 main 祖先 | ✅ 成立 |

## 文档中引用 grep 证据的句子（3 处，人工复核索引）

- `docs/research/concurrent-write-forensics-2026-11-02.md:152: | D | `grep -rla "TestSanshaScope\|jianxiang" tests/`（复现 Q-020 假阴性） | 空（复现） |`
- `docs/research/concurrent-write-forensics-2026-11-02.md:155: > 附带修正：此前某轮 `grep -ac "" core-eval/src/core_eval/engine.py` 输出空、`
- `docs/research/concurrent-write-forensics-2026-11-02.md:164: 2. "grep 无输出"仍然**不是**"不存在"的证据——只是理由从"判二进制"改为`

> 本表由脚本生成；新增「grep 零命中」类结论时请同步登记到 FINDINGS。
