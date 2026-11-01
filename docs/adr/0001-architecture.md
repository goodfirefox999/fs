# ADR-0001：分层架构与零第三方依赖策略

- 状态：已采纳
- 日期：2026-11-01
- 决策者：实现者（Agent），待人类复核

## 背景

上游两份规格在架构上一致（事实层/符号层/规则层/判定层/应用层），但在数据模型与排序策略上有分歧。
同时，规格建议使用 `pydantic v2` 与 `skyfield`，而本项目要求**运行时完全离线、可复现、低依赖**。

## 决策

1. **采用五层单向依赖**：`app-zeri → core-eval → core-rule → core-symbol`，`core-symbol` 与 `core-time` 之间
   通过参数注入解耦（不直接 import），避免循环依赖并让符号层可独立测试。
2. **核心五包仅依赖标准库**。唯一外部依赖是 `pyyaml`（规则库解析）。
3. **不使用 pydantic**：数据模型用 `dataclass(frozen=True)` + 显式校验函数（`loader.py`）。
   JSON Schema 手写（`app-zeri/schemas.py`），契约测试用 40 行极简校验器。
4. **不使用 skyfield**：自实现 VSOP87D 截断（见 ADR-0002）。

## 理由

- `pydantic` 与 `skyfield` 会引入编译型二进制依赖（`pydantic-core`、`numpy`、星历文件），
  与"离线、可复现、单一文件即可运行"的目标冲突；星历文件还需版本锁定与分发许可。
- 手写校验函数反而更容易表达"待考证规则不得进入判定"这类**业务约束**，
  而这些约束在 `pydantic` 中需要用 `model_validator` 绕一圈。
- 代价：JSON Schema 与校验逻辑需手工同步。缓解措施：`test_contract.py` 断言 schema 与实现一致。

## 后果

- ✅ 安装即用（`pip install pyyaml` 即可跑全部测试），CI 快，无二进制兼容问题。
- ✅ 校验错误信息可精确指向规则 id 与字段路径。
- ⚠️ 失去 pydantic 的自动序列化与 IDE 补全；需靠类型注解 + 测试保证。
- ⚠️ 若将来引入 FastAPI，请求/响应模型需再评估是否引入 pydantic（届时属 M10，另行 ADR）。

## 备选方案

| 方案 | 否决理由 |
|---|---|
| 全量采用 pydantic | 二进制依赖 + 与离线目标冲突 |
| 用 `attrs` | 同样引入外部依赖，收益不明显 |
| 用 `TypedDict` | 无运行期校验，无法承载业务约束 |
