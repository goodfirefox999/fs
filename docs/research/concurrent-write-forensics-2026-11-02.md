# 并发写入取证与处置（2026-11-02 23:45）

> 触发：Phase 11 执行期间发现 `core-symbol/` 下有**非本会话创建**的文件（22:52–22:53），
> 且 `__init__.py`、`shensha.py`、`mountain.py` 在同一时段被改动。
> 本文是取证记录 + 风险判定 + 处置，不是推测。凡无法取证的项目显式标「不可得」。

## 一、取证（命令与结果）

| 命令 | 目的 | 结果 |
|---|---|---|
| `git status --porcelain=v1` | 工作区全貌 | 32 个已跟踪文件被改 + 70 个未跟踪文件；**没有任何 commit 包含本轮改动** |
| `git log --since=2026-11-01 --oneline --all` | 提交历史 | HEAD = `64f5be5`（Phase 10 收口）。**本轮所有产出均未提交**，不存在"被裹进 commit"的事实 |
| `git diff --stat HEAD` | 变更规模 | 32 files changed, 1273 insertions(+), 314 deletions(-) |
| `ls -la -T`（目录级） | 时间戳归属 | 见第二节 |
| `ps aux` | 查并发进程 | **不可得**：沙箱返回 `operation not permitted` |
| `ls -la -T tools/` | 二次取证 | `tools/determinism_probe.py` 的 mtime = **23:45:19**，即在写本文前一刻仍在产出 → **另一进程当时仍活跃** |

## 二、时间戳归属（哪些不是我写的）

| 文件 | mtime | 归属 | 证据 |
|---|---|---|---|
| `core-symbol/.../doushou.py` | 21:26 | 上一会话（Phase 9，未提交） | 早于本会话起始 22:19 |
| `core-rule/rules/doushou/*.yaml` | 21:2x | 上一会话 | 同上 |
| `core-symbol/.../zibai.py` | 22:55 | **本会话**（时盘拆分 + 复核提示） | 本会话编辑 |
| `core-symbol/.../xiu.py` / `jishen.py` | 22:28 / 22:30 | **本会话**（新建） | 本会话编辑 |
| `core-symbol/.../jianchu.py` | 22:52 | **他进程** | 本会话未创建；docstring 引用不存在的 `tests/unit/test_paipan_fixed.py`（该文件 22:5x 后出现） |
| `core-symbol/.../huangdao.py` | 22:53 | **他进程** | 同上 |
| `core-symbol/.../shensha.py` | 22:55 | **他进程**（新增 `wuhuang_year_of_date`） | 本会话未改该文件 |
| `core-symbol/.../mountain.py` | 22:56 | **他进程**（兼向 9°/3° vs 6°/4.5° 两说文档化） | 本会话未改该文件 |
| `core-symbol/.../__init__.py` | 22:56 | **他进程**（导出 huangdao/jianchu/wuhuang_year_of_date） | 本会话未改该文件 |
| `docs/research/paipan-roadmap-2026-11.md` | 22:5x | **他进程** | 本会话未写 |
| `tests/unit/test_paipan_fixed.py` | 22:5x | **他进程** | 本会话未写 |
| `tools/determinism_probe.py` | 23:45 | **他进程** | 写本文时刚出现 |

结论：**同一工作区至少有两个 agent 在写**，分工大致是「他进程：建除/黄道/五黄宫级/兼向口径 + 确定性探针；
本会话：紫白接入/值宿/吉神 + 两条机器门禁」。两边改动恰好不冲突。

## 三、“测试全绿”证明了什么、没证明什么

- **证明**：合并后的工作树在 978 个用例上通过；两条改动线在**语法层与行为层**都不冲突。
- **没证明**：
  1. 语义层不冲突 —— 例：他把「五黄命中山级 vs 宫级」改了实现，我新增的
     `facts.zibai.*.wuhuang_hit_mountain` 若按山名精确匹配就与他的宫级口径不一致；
  2. 计数一致 —— `rules_manifest.yaml`（我改到 85 条）在他再加规则时会立刻 lint 失败；
  3. 审计链完整 —— **Q-015~Q-017 是我登记的，他未参与**；若他后续也登记 Q-018，
     编号会撞车（他已把「五黄命中粒度」写成 Q-018）；
  4. 可复现 —— 报告里的 `input_hash` 只覆盖输入，不覆盖"哪一版工作树"。

## 四、三条具体风险与处置

| 风险 | 现状 | 处置 |
|---|---|---|
| 未提交改动被误裹进 commit | 当前**未发生**（HEAD 仍是 64f5be5，无新提交） | 提交前先跑 `tools/worktree_guard.py`（本轮新增）；一次提交只含本会话白名单 |
| 他进程基于旧版本写文件 → 逻辑冲突但语法通过 | **已存在同类面**：两套五黄实现并存（他的 `wuhuang_year_of_date` vs 我的 `facts.zibai.*.wuhuang_hit_mountain`） | 在 `docs/QUESTIONS.md` 或 ADR 里指定**单一事实源**；本轮不动他的实现，只登记冲突点 |
| 裁定记录对不上（Q 编号/登记交叉） | Q-015~Q-017 由本会话登记；他占用 Q-018（五黄粒度） | 后续新增 Q 前先 `grep "^## Q-" docs/QUESTIONS.md` 取最大号 +1，禁止凭记忆编号 |

## 五、结论（写入流程，不再是“下次注意”）

1. **单写者原则**：同一工作区同时只允许一个 agent 写文件；需要并行时按目录分片
   （如 `core-symbol/` vs `app-zeri/`），并在任务开始时声明分片。
2. **提交前守卫**：`tools/worktree_guard.py` 列出未跟踪/未提交文件，非白名单即警告。
3. **裁定编号唯一性**：新增 Q 前必须 `grep` 现有最大编号，禁止凭记忆。
4. **`ps` 不可得**：沙箱禁止查看进程表，进程取证只能靠**文件 mtime**（本轮即用此法锁定他进程活跃到 23:45）。


---

## 六、追加取证：三个热文件是否被"写了至少两遍"（2026-11-03 00:50）

### 6.1 命令与结果

| 命令 | 结果 |
|---|---|
| `git log --oneline -1` | `64f5be5`（Phase 10 收口）——**三次会话的改动全部在工作区，未提交** |
| `git stash list` | 仅 `stash@{0}`（`WIP on (no branch): eac493d`，11-01 的旧 WIP，与本轮无关） |
| `git diff --stat HEAD -- core-eval/ core-rule/ app-zeri/` | 19 files, +831/−110；其中 `engine.py +111`、`ranker.py +33/−…`、`arbitration.py +11` |
| AST 扫描（`tests/unit/test_no_total_rank.py`） | `_total_rank` / `_mean_rank_score` 在 `engine.py`、`ranker.py` 的**语法树中已不存在** |

### 6.2 三个关键符号的实际状态

| 符号 | 状态 | 位置 |
|---|---|---|
| `_total_rank` / `_mean_rank_score` | **已删除**（仅在 engine.py 注释里留历史说明 + `tools/check_no_aggregate_score.py` docstring 引用） | 无定义、无调用 |
| `consensus_ratio` / `non_voters` / `gate_veto_schools` / `_consensus_detail` | **存在且贯通**：engine 产出 → arbitration 透传 → report 渲染 → 测试断言 | `engine.py:1149–1197`、`arbitration.py:69+`、`report.py:248+` |
| `reference` 桶 / `engine_eligible` | **存在且贯通**：rule 字段 → loader 校验 → engine 分桶 → report 参考层节 | `models.py`、`engine.py`、`report.py` |

三者**同时存在**，说明不是"最后一次写入把前面覆盖掉"——若是覆盖，必有一方的符号消失。

### 6.3 但"没有覆盖"只能这样证明，不能更强

`git diff HEAD` 是**相对 Phase 10 的一次性合并差异**，它无法把某一行归给某一次会话。
所以能给出的结论只有两条，必须分开说：

1. **可证**：三家的签名符号在同一棵树上共存且互相贯通（上表），不存在整文件级覆盖。
2. **不可证**：每一行的最终形态是否等于"三次改动的叠加"。若两次改动落在同一函数同一行，
   后者会静默胜出——这类冲突只能靠**逐函数 review**发现，git 帮不上。

### 6.4 抓到的真实覆盖形态：文档编号撞车（不是代码）

`docs/QUESTIONS.md` 曾同时存在 `## Q-018`、`## Q-020`、`## Q-021` **各两份**
（一份是问题本体，一份是另一会话写的「处置更新」）。后果不是代码错，而是：
`grep '^## Q-' | tail -1` 取最大号会取到重复号，下一份裁定记录可能覆盖或撞号。

处置：

- 三处「处置更新」改为 `## 处置更新 · Q-nnn …`（不再以 `## Q-nnn` 开头）；
- 新增 lint 不变式 `check_question_numbering`（重复/断号即失败）+ 6 例反证测试；
- 文件头写入编号纪律。

**这条正是"合并后测试全绿但审计链已坏"的实例**：测试不读文档，永远不会红。

### 6.5 结论

- 三个热文件**没有**被整文件覆盖；`_total_rank` 已彻底删除（AST 级证明 + 行为级 `sort_key` 测试）。
- 真正的并发损伤发生在**文档/编号层**，已修复并加门禁。
- `ps`/`lsof` 仍不可得；身份无法确认，只能以 mtime + 符号共存性作为间接证据。

### 6.6 只读核对 Q-020 / Q-021：一次险些误报的 "grep 假阴性"（**2026-11-03 根因修正**）

> ⚠️ **本节最初的根因诊断是错的，现予更正。** 原诊断称"部分 .py 含让 GNU grep
> 判为二进制的字节，grep 静默跳过该文件"。2026-11-03 用字节级扫描复查：
> **全仓 .py 含 NUL 字节 0 个、非 UTF-8 0 个**——文件本身没有任何编码问题。
> 真正的根因见下。保留错误诊断的历史是因为它演示了"第一解释 ≠ 正确解释"。

按要求核对"另一会话宣称已落地"的两项。第一遍用 shell：

```bash
grep -rn "TestSanshaScope\|jianxiang\|jian_caliber" tests/ core-rule/ app-zeri/
# 输出：空
```

差一点据此写"宣称与树不一致"。改用 Python 遍历后，结果相反（**结论不变，以下为最终版**，
由 `tools/verify_claims.py` 可复跑，归档见 `docs/research/q020-q021-verification.md`）：

| 宣称 | 实际 | 结论 |
|---|---|---|
| Q-020「已上锁」 | `tests/unit/test_paipan_fixed.py::TestSanshaScope` 4 例（含 `test_ren_mountain_is_not_sansha_hit`），全通过 | **属实** |
| Q-021「已解耦为数值口径」 | `core-rule/config/calibers/jianxiang.yaml`（两口径 + `threshold_deg` 参数）+ `TestJianxiangCaliber` 5 例，全通过 | **属实** |

**真正根因（2026-11-03 对照实验坐实）**：本沙箱的 `grep` 是 **toybox 0.8.13**
（`grep --version` → `toybox 0.8.13 (is not GNU grep 9.0)`）。toybox 的 BRE
**不支持 `\|` 交替**——模式 `A\|B` 被当作字面量 "A|B" 去匹配，于是**静默零匹配**：
不报错、不提示，看起来就像"不存在"。

对照实验（`tools/verify_claims.py --demo` 可复跑）：

| 实验 | 模式 | 结果 |
|---|---|---|
| A | `grep -ac "HIT_BUCKETS" tools/dead_rule_scan.py`（BRE 单模式） | 5 次命中 ✓ |
| B | `grep -ac "def \|HIT_BUCKETS" …`（BRE `\|`） | **0**（假阴性） |
| C | `grep -acE "def \|HIT_BUCKETS" …`（`-E`） | 16 次命中 ✓ |
| D | `grep -rla "TestSanshaScope\|jianxiang" tests/`（复现 Q-020 假阴性） | 空（复现） |
| E | 同 D 换 `-E "TestSanshaScope\|jianxiang"` | 命中 `test_paipan_fixed.py` ✓ |

> 附带修正：此前某轮 `grep -ac "" core-eval/src/core_eval/engine.py` 输出空、
> `file` 把它判成 "data"，曾导向"engine.py 被当作二进制"的猜想。那也是 toybox
> 的怪癖（空模式计数），文件本身正常。**所有"输出异常 → 判定文件损坏"的推理链
> 都应当先排除工具实现差异。**

**纪律（取代本节最初的版本）**：

1. 交替模式**必须** `grep -E "A|B"`（或 Python 遍历）；`\|` 只在 GNU grep 可用，
   toybox/BSD grep 下静默零匹配。已写入 `AGENTS.md` 约束第 9 条。
2. "grep 无输出"仍然**不是**"不存在"的证据——只是理由从"判二进制"改为
   "正则方言 + 工具实现差异"。存在性核对的首选永远是 Python（`verify_claims.py`
   是模板）。
3. `git log`/`grep`/`sed` 等外部命令在沙箱与真机可能不同实现；跨环境复现
   "异常空输出"时，先打 `--version`。
   （本次若直接采信 grep，就会制造一起"指控他人虚报"的假事故。）
