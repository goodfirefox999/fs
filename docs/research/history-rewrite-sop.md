# 历史重写 SOP（与 verification-patterns.md 并列的操作模板）

> 2026-11-03 首次执行（重写 4 提交分片链）后固化；执行工具为
> `tools/verify_rewrite_chain.py`，本 SOP 是它的操作规程与教训清单。

## 什么时候允许重写

- 仅当**重写理由成立且不可用追加提交替代**：如"中间提交单独检出必红"
  （bisect 会走到红档，追加 fixup 只救 tip 不救链）。
- 重写是**特权操作**：多会话环境下改历史风险大于收益（评审曾明确反对）。
  放行条件 = 三重护栏齐备（见下），缺一不改。

## 三重护栏（动手前必须全部就位）

1. **旧链不可达防护**：打 tag（如 `backup/pre-rewrite-<日期>`）+ 落 bundle
   （`git bundle create ../<repo>-backup-<阶段>-<日期>.bundle --all`）。
   bundle 必须复制到**仓库目录之外**（同一父目录不算备份——同盘同删），
   并 `git bundle verify` 逐份验证；异机/异介质是唯一真闭环。
2. **旧链位置确认**：`git log origin/main --oneline -1` 确认旧链是否上过远端。
   - 未上过（本轮情形）：push 顺序无特殊要求；
   - 上过：**先**推 `backup/…` 分支/tag 保旧链，**再**推新链，顺序反了旧链即丢。
3. **stash 盘点**：`git stash list` + 逐条 `git merge-base --is-ancestor <base> <新链tip>`
   验证 stash base 在新链可达；不可达的 stash 要在重写前显式导出
   （`git stash show -p > …`）。

## 重写流程（本轮实证版本）

```bash
# 1) 双备份
git tag backup/pre-rewrite-<日期> <旧tip>
git bundle create ../<repo>-backup-before-fixup-<日期>.bundle --all

# 2) 在新分支重建（worktree 方式隔离主工作区）
git checkout -B repair <旧基底>
#   逐片恢复内容：git checkout <旧SHA> -- <文件/目录>
#   应用修复（如剥离仓库级断言）后逐片 commit -C <旧SHA>   # 复用原提交信息

# 3) 逐 SHA 独立验证（关键步——「tip 绿」不等于「链绿」）
python tools/verify_rewrite_chain.py --base <旧基底> --tip repair --with-lint
#   - 每 SHA 独立 worktree + junitxml（-q 下汇总行不可见，XML 是权威数字）
#   - 任何一档红 → 修内容后重来，不许跳过
#   - 默认分批（每批 3 个 SHA，短命子进程），避免全链单进程被 SIGKILL(137)
#   - --with-lint 可选；默认不跑（lint 是独立门禁，且抬高单批资源占用）

# 4) 切换分支指针 + 清理
git branch -f main repair && git checkout main && git branch -D repair
git worktree prune
git bundle create ../<repo>-backup-post-rewrite-<日期>.bundle --all
```

## 已知坑（全部在本轮实际踩过）

| 坑 | 症状 | 防御 |
|---|---|---|
| `git checkout <旧SHA> -- .` 恢复**整棵树** | 后片把前片的修复悄悄回滚（本轮：片4 把片1 剥离的断言带了回来） | 恢复后立即对关键文件做内容断言；恢复范围尽量窄（只 checkout 需要的路径） |
| subprocess 列表传 `-m` 两段 | `-m "not" "slow"` → pytest 把 `slow` 当路径：`file or directory not found: slow` | 传单参数 `"not slow"`（verify_rewrite_chain 首版即中招，靠自跑抓出） |
| worktree 残留 | 上次运行被 SIGKILL → `fatal: already exists` | 脚本创建前先 `remove --force` + rmtree |
| pytest 汇总行 | `-q` 下 stdout 无汇总（AGENTS 约束 10） | 一律 junitxml + `summarize_junit.py` |
| verify 脚本漏传 PYTHONPATH | worktree 内 0 collected | subprocess 显式 `env=PYTHONPATH=…`（教训：worktree 不继承主仓库 venv 的路径假设） |
| **全链单进程被 SIGKILL** | 跑 `--base … --tip …` 中途 `exit 137`，且残留 worktree 让下次报 `already exists` | **默认分批**（`--batch-size`，默认 3，每批一个短命子进程，批间 prune）；`--all-at-once` 才一次跑完。默认**不跑 lint**——lint 抬高单批占用且本身是独立门禁（`make lint`）。撞 137 时先怀疑资源上限，不要先怀疑工具逻辑 |

## 验收定义

- `verify_rewrite_chain --base <基底> --tip <新tip>` 输出**全链逐 SHA 独立绿**；
- 三份备份（tag + before/after bundle）在仓库外目录存在且 `git bundle verify` 通过；
- stash 全部 base 可达；远端处置（push 新链 / backup tag）按第 2 步的确认执行。
