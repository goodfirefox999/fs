# 待应用补丁：`verdict_type: null` → `"unspecified"`（2026-11-03）

> **状态：未应用。** 原因：`core-rule/src/core_rule/models.py`、`loader.py`、`app-zeri/.../report.py`
> 是三个会话都动过的热文件；本轮已完成取证（见 `concurrent-write-forensics-2026-11-02.md`），
> 但**逐行归属仍不可证**。按"单写者 + 热文件先确认"原则，本补丁先落成文档，
> 等热文件归属确认后一次性应用。

## 一、问题

`Rule.effective_verdict_type` 当前的推断规则是：

```python
if self.verdict_type:
    return self.verdict_type
if self.hard_veto and self.severity == "禁用":
    return "gate"
return "vote"          # ← 问题在这里
```

后果：**"没人管过"被静默归成"投票"**。报告上 `vote` 与 `unspecified` 长得一样，
但两者含义相反：

| 实际状态 | 当前显示 | 应该显示 |
|---|---|---|
| 明确设计为投票 | `vote` | `vote` |
| 从没人给它定过性 | `vote` | `unspecified` |

这正是本项目最忌讳的形态：**把"未决"伪装成"已分类"**。迁移期允许不标，但必须看得见。

## 二、补丁内容（三处，均向后兼容）

### 2.1 `core-rule/src/core_rule/models.py`

```python
    @property
    def effective_verdict_type(self) -> str:
        """生效判定类型；**未标注返回 "unspecified"，不猜 "vote"**。

        为什么不再兜底成 vote（2026-11-03）：
        兜底会让"没人管过"与"明确设计为投票"在报告上无法区分——前者是待办，
        后者是结论。把未决伪装成已分类，比留空更难发现。
        """
        if self.verdict_type:
            return self.verdict_type
        if self.hard_veto and self.severity == "禁用":
            return "gate"          # 硬否定按定义就是闸门，可推断
        return "unspecified"       # 其余一律不猜
```

**注意**：`gate` 的推断保留。理由：`hard_veto=True + severity=禁用` 在语义上**只能**是闸门，
这是定义级推断而非猜测；而 `vote` 不是——`可用/推荐/慎用` 都可能只是"暂未归类"。

### 2.2 `core-rule/src/core_rule/loader.py`（新增一条 lint 级约束）

不新增必填字段（迁移期），只在**显式写成字符串 `"unspecified"`** 时拒绝：

```python
    if verdict_type == "unspecified":
        raise DSLValidationError(
            "verdict_type 不接受显式 'unspecified'：未归类请省略该字段，"
            "由 effective_verdict_type 推断（避免把待办写成结论）",
            rule_id=rule_id,
        )
```

### 2.3 `app-zeri/src/app_zeri/report.py`（新增「未归类」节）

在「派别判定明细」之后追加：

```python
    unlabeled = sorted({j.rule_id for j in ev.judgments if j.verdict_type is None})
    if unlabeled:
        lines.append("**未归类规则（verdict_type 未标注，按 severity 路由）**")
        lines.append("")
        lines.append(
            f"共 {len(unlabeled)} 条：{'、'.join(f'`{r}`' for r in unlabeled[:12])}"
            + ("…" if len(unlabeled) > 12 else "")
        )
        lines.append("")
        lines.append(
            "> 未归类 ≠ 投票。这些规则当前按 `severity`/`hard_veto` 走既有路由，"
            "行为与标注前一致；C 第二批迁移时逐条定为 gate / vote / reference。"
        )
        lines.append("")
```

## 三、为什么这样改而不是"全库强制标注"

- 全库 86 条强制标注 = 一次空迁移，且必然有 60+ 条被随手写成 `vote`——那只是把
  "未归类"批量伪装成"已归类"，比现在更糟。
- `unspecified` 的价值在于**可计数**：`rules lint` 已经有
  "verdict_type 未标注 N 条" 的 warning，报告再列一节，未归类就是一条**可见的待办队列**。

## 四、应用后必须同批更新的测试

| 测试 | 改动 |
|---|---|
| `tests/unit/test_rule_verdict_type.py::TestLoaderContract::test_effective_verdict_type_inferred` | 末行断言由 `== "vote"` 改为 `== "unspecified"` |
| 同上 `test_defaults_are_backward_compatible` | 不变（字段仍为 None） |
| 新增 | `test_explicit_unspecified_is_rejected`（loader 拒绝显式字符串） |
| 新增 | `test_gate_inference_survives`（硬否定仍推断为 gate） |
| `tests/unit/test_report_*` | 若断言报告节数，需加「未归类」节 |

## 五、应用前检查清单

1. `git status --porcelain` 里 `models.py`/`loader.py`/`report.py` 的 mtime 是否早于本会话最后一次编辑；
2. 若他进程仍在写 → **不应用**，先在 `docs/QUESTIONS.md` 登记"待应用补丁"并注明 blocker；
3. 应用后跑 `pytest tests/unit/test_rule_verdict_type.py tests/unit/test_report_zero_voter.py -q`
   与 `zeri rules lint`；
4. 在 CHANGELOG 记一行"未归类不再兜底为 vote"。

## 六、与 C 批次的顺序

```
C 第一批（已完成）：10 条显式标注 + reference 桶 + 三条 lint 不变式
        ↓
本补丁（待应用）：未标注 → unspecified（可见化），行为不变
        ↓
C 第二批：按「未归类」队列逐条定 gate/vote/reference（一次 10–15 条，可回滚）
```

**顺序不能反**：先做第二批再改 `unspecified`，等于在"已归类"的假象上做归类。
