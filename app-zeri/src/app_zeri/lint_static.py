"""静态一致性检查（应用层 lint 用）：抓「代码存在但没接上」与「登记与代码互相打脸」。

为什么需要这一层
----------------
2026-11-02 的事故形态不是"算错"，而是**模块写好了、测试也过了、但从未被调用**：
``derive_zibai_facts`` 躺在盘上，``facts.zibai`` 不存在，规则无法引用；
与此同时 ``coverage_gaps.yaml`` 写"未实现"、README 也写"未实现"——三处互相矛盾
还能共存一个阶段。运行期测试抓不到它，因为"没接上"不会让任何断言失败。

两条不变式（本模块只做静态分析，不执行引擎）
------------------------------------------
1. **死代码**：``core-symbol/`` 下每个公开 ``derive_*`` 函数必须至少有一个
   **定义文件之外**的调用点；每个非 ``__init__`` 模块必须被至少一个非测试文件 import。
2. **登记一致性**：``coverage_gaps.yaml`` 里每条登记带 ``implementation`` 块，
   声明 ``status`` 与期望的 ``fact_roots`` / ``derive``；lint 用 ``FACT_REGISTRY``
   与静态调用点核对——标 ``unimplemented`` 却已注册事实或已有调用点 → 失败；
   标 ``implemented`` 却查不到事实或调用点 → 也失败。

两条都配反证测试（``tests/unit/test_lint_static.py``）：构造违规样本断言报警 +
移除触发条件断言沉默。只测"恰好为空"不算验证（AGENTS 纪律 3）。
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = [
    "DeriveSite",
    "RepoIndex",
    "build_index",
    "dead_derive_functions",
    "unimported_modules",
    "check_coverage_gaps",
    "check_question_numbering",
    "check_demo_veto_wiring",
]

#: 参与扫描的源码根（相对仓库根）。测试与工具脚本**不**算调用点。
SOURCE_ROOTS: tuple[str, ...] = (
    "core-time/src",
    "core-symbol/src",
    "core-rule/src",
    "core-eval/src",
    "app-zeri/src",
)

#: 符号层模块清单的扫描目录（死代码检查只针对这一层，其余层由各自 lint 负责）
SYMBOL_ROOT = "core-symbol/src/core_symbol"


@dataclass(frozen=True)
class DeriveSite:
    """一个 ``derive_*`` 函数的定义位置与调用点数量。"""

    module: str
    name: str
    path: Path
    external_calls: int
    internal_calls: int
    #: 是否可从「定义文件之外」到达（含同文件内被活函数间接调用）
    reachable: bool = False

    @property
    def is_dead(self) -> bool:
        return not self.reachable


@dataclass(frozen=True)
class RepoIndex:
    """一次静态扫描的结果（只读）。"""

    derives: tuple[DeriveSite, ...]
    imported_modules: frozenset[str]
    symbol_modules: frozenset[str]

    def derive_by_name(self, name: str) -> DeriveSite | None:
        for site in self.derives:
            if site.name == name:
                return site
        return None

    def call_count(self, name: str) -> int:
        site = self.derive_by_name(name)
        return site.external_calls if site else 0


def _iter_py(root: Path) -> Iterable[Path]:
    if not root.exists():
        return ()
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - 语法错误由测试兜底
        return None


def _public_derives(tree: ast.Module) -> list[str]:
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("derive_"):
            out.append(node.name)
    return out


def _called_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _imported_modules(tree: ast.Module) -> set[str]:
    """收集 ``from .x import`` / ``import pkg.x`` 的末段模块名。"""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.module or node.module and node.module.startswith("core_symbol"):
                out.add(node.module.split(".")[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("core_symbol"):
                    out.add(alias.name.split(".")[-1])
    return out


def _calls_by_function(tree: ast.Module) -> dict[str, set[str]]:
    """顶层函数名 → 该函数体内调用的名字集合（含模块级代码，键为 ``"<module>"``）。"""
    out: dict[str, set[str]] = {}
    module_level: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = _called_names(node)
        else:
            module_level |= _called_names(node)
    out["<module>"] = module_level
    return out


def build_index(repo_root: Path) -> RepoIndex:
    """扫描源码树，产出 ``derive_*`` 可达性与模块导入面。

    可达性定义：从**定义文件之外**的调用点出发，沿同文件内的调用图做传递闭包。
    只数"外部直接调用"会误报"被同文件活函数调用的内层 helper"；只数"任意调用"
    又会漏报"自己调自己、外面没人调"的死模块。传递闭包是这两端之间的唯一正确口径。
    """
    files: list[Path] = []
    for rel in SOURCE_ROOTS:
        files.extend(_iter_py(repo_root / rel))

    calls_by_file: dict[Path, set[str]] = {}
    graph_by_file: dict[Path, dict[str, set[str]]] = {}
    imports: set[str] = set()
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        calls_by_file[path] = _called_names(tree)
        graph_by_file[path] = _calls_by_function(tree)
        imports |= _imported_modules(tree)

    # 定义表：函数名 → 定义所在文件（同名定义理论上只出现在一个文件）
    defs: dict[str, set[Path]] = {}
    for path, funcs in graph_by_file.items():
        for fname in funcs:
            if fname != "<module>":
                defs.setdefault(fname, set()).add(path)

    # 种子：① 被**定义文件之外**调用；② 同文件模块级代码里的调用（import 即执行）
    alive: set[str] = set()
    for path, names in calls_by_file.items():
        module_level = graph_by_file.get(path, {}).get("<module>", set())
        for name in names:
            defined_in = defs.get(name)
            if not defined_in:
                continue
            if any(d != path for d in defined_in) or name in module_level:
                alive.add(name)

    # 传递闭包：同文件内「活函数调用到的名字」也活
    changed = True
    while changed:
        changed = False
        for funcs in graph_by_file.values():
            for func_name, callees in funcs.items():
                if func_name == "<module>" or func_name in alive:
                    for callee in callees:
                        if callee not in alive:
                            alive.add(callee)
                            changed = True

    symbol_dir = repo_root / SYMBOL_ROOT
    symbol_modules = {p.stem for p in _iter_py(symbol_dir)}
    derives: list[DeriveSite] = []
    for path in _iter_py(symbol_dir):
        tree = _parse(path)
        if tree is None:
            continue
        for name in _public_derives(tree):
            external = sum(
                1 for other, names in calls_by_file.items() if other != path and name in names
            )
            internal = 1 if name in calls_by_file.get(path, set()) else 0
            derives.append(
                DeriveSite(
                    module=path.stem,
                    name=name,
                    path=path,
                    external_calls=external,
                    internal_calls=internal,
                    reachable=name in alive,
                )
            )
    derives.sort(key=lambda d: d.name)
    return RepoIndex(
        derives=tuple(derives),
        imported_modules=frozenset(imports),
        symbol_modules=frozenset(symbol_modules - {"__init__"}),
    )


def dead_derive_functions(index: RepoIndex) -> list[str]:
    """返回"零外部调用点"的 ``derive_*`` 函数说明（空列表 = 通过）。"""
    return [
        f"{d.module}.{d.name} 无定义文件之外的调用点（死代码：写了但没接上）"
        for d in index.derives
        if d.is_dead
    ]


def unimported_modules(index: RepoIndex) -> list[str]:
    """返回"未被任何非测试文件 import"的符号层模块（空列表 = 通过）。"""
    return [
        f"core_symbol.{name} 未被任何非测试文件 import（模块存在但不在调用链上）"
        for name in sorted(index.symbol_modules - index.imported_modules)
    ]


def check_coverage_gaps(
    gaps_path: Path,
    *,
    fact_registry: Iterable[tuple[str, str]],
    index: RepoIndex,
) -> list[str]:
    """登记与代码一致性。``fact_registry`` 传 ``(fact_name, provider)`` 序列。

    判定口径（与 ``coverage_gaps.yaml`` 的 ``implementation`` 块对应）：

    - ``unimplemented``：``fact_roots`` 必须**都不提供**（未登记或 provider=「本系统不提供」），
      且 ``derive`` 列出的函数必须零外部调用点；
    - ``implemented``：``fact_roots`` 至少一个**已提供**，且列出的每个 ``derive`` 都有调用点。
    """
    if not gaps_path.exists():
        return []
    data = yaml.safe_load(gaps_path.read_text(encoding="utf-8")) or {}
    provided = {name for name, provider in fact_registry if provider != "本系统不提供"}
    known = {name for name, _ in fact_registry}

    def _fact_present(root: str) -> bool:
        return any(name == root or name.startswith(root + ".") for name in provided)

    problems: list[str] = []
    for gap in data.get("gaps") or []:
        impl = gap.get("implementation")
        if not impl:
            continue
        gid = gap.get("id", "?")
        status = impl.get("status")
        roots = [str(r) for r in (impl.get("fact_roots") or [])]
        derives = [str(d) for d in (impl.get("derive") or [])]

        if status == "unimplemented":
            for root in roots:
                if _fact_present(root):
                    problems.append(
                        f"{gid}: 登记为「未实现」，但 facts.{root} 已在 FACT_REGISTRY 提供"
                        "（登记与代码不一致，需更新 coverage_gaps 或撤下实现）"
                    )
                if root not in known and root.count(".") == 0:
                    continue  # 完全未登记 = 未实现，符合预期
            for name in derives:
                if index.call_count(name) > 0:
                    problems.append(
                        f"{gid}: 登记为「未实现」，但 {name} 已有调用点"
                        f"（{index.call_count(name)} 处）——死代码门禁与登记冲突"
                    )
        elif status == "implemented":
            if roots and not any(_fact_present(r) for r in roots):
                problems.append(
                    f"{gid}: 登记为「已实现」，但 facts.{roots} 均未在 FACT_REGISTRY 提供"
                )
            for name in derives:
                if index.call_count(name) == 0:
                    problems.append(
                        f"{gid}: 登记为「已实现」，但 {name} 无调用点——"
                        "这正是 2026-11-02 死模块事故的形态"
                    )
        else:
            problems.append(f"{gid}: implementation.status 非法（{status}），只允许 implemented/unimplemented")
    return problems


def check_question_numbering(questions_path: Path) -> list[str]:
    """``docs/QUESTIONS.md`` 的 Q 编号必须唯一且连续（审计链完整性）。

    为什么归到 lint
    --------------
    「新增条目编号 = 现有最大号 + 1」这条纪律，靠人记必然撞车：本轮 Q-018/Q-020/Q-021
    各出现两次（不同会话同时追加），而**没有任何门禁会发现**——报告照出、测试照绿，
    直到有人拿着两份编号不同的裁定记录对不上。

    判据：
    - 重复编号 → 失败（同一号可能对应两份互斥裁定）；
    - 区间内断号 → 失败（条目被删，审计链断了）。
      处置更新请用 ``## 处置更新 · Q-nnn …``，不以 ``## Q-nnn`` 开头。
    """
    import re

    if not questions_path.exists():
        return []
    text = questions_path.read_text(encoding="utf-8")
    ids = re.findall(r"^## (Q-(\d+))", text, flags=re.M)
    if not ids:
        return []
    names = [name for name, _ in ids]
    numbers = [int(num) for _, num in ids]

    problems: list[str] = []
    seen: dict[str, int] = {}
    for name in names:
        seen[name] = seen.get(name, 0) + 1
    dups = sorted(n for n, c in seen.items() if c > 1)
    if dups:
        problems.append(
            f"QUESTIONS: 编号重复 {dups}——同一号可能对应两份互斥裁定（新增前先 grep 最大号）"
        )
    lo, hi = min(numbers), max(numbers)
    missing = [f"Q-{i:03d}" for i in range(lo, hi + 1) if i not in set(numbers)]
    if missing:
        problems.append(f"QUESTIONS: 区间断号 {missing}——条目被删或跳号，审计链不完整")
    return problems


def check_demo_veto_wiring(repo_root: Path) -> list[str]:
    """联调开关 ``demo_veto`` 只允许两条通路：CLI 显式传参、测试显式构造 ``EvalConfig``。

    为什么是门禁而不是约定
    ----------------------
    ``demo_veto=True`` 会让未考证规则的演示命中恢复"有票权"（ADR-0014 决策 3 的
    显式联调例外）。这个开关一旦腐化——有人为了"让报告好看"加一个环境变量、
    或把 true 写进配置默认值——生产路径就会静默带演示票，而报告顶部的横幅
    反而会让人以为"有横幅=已被告知=没问题"。

    两条硬禁止（2026-11-03 评审第四节）：

    1. 源码里**不得**从环境变量读它（``os.environ`` / ``os.getenv`` 出现
       ``DEMO_VETO`` 字样）——环境变量是最容易无意设置的通路；
    2. ``core-rule/config/`` 与 ``app-zeri`` 的配置 YAML **不得**出现
       ``demo_veto`` 键——开关只存在于 CLI 参数与测试代码，配置层不认识它。

    违反任意一条即 fail（阻断，不是警告）。
    """
    import ast as _ast

    problems: list[str] = []

    src_roots = ("core-eval/src", "app-zeri/src", "core-rule/src")
    for rel in src_roots:
        root = repo_root / rel
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                tree = _ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            rel_path = path.relative_to(repo_root)

            def _is_environ(node: _ast.AST) -> bool:
                """os.environ / environ（含 os.environ.get 的 value 链）。"""
                if isinstance(node, _ast.Attribute):
                    return node.attr == "environ" or _is_environ(node.value)
                return isinstance(node, _ast.Name) and node.id == "environ"

            def _flag(lineno: int, form: str) -> None:
                problems.append(
                    f"{rel_path}:{lineno}: 禁止从环境变量读取 demo_veto（{form}）"
                    "（只允许 CLI 传参 / 测试显式构造 EvalConfig）"
                )

            for node in _ast.walk(tree):
                if isinstance(node, _ast.Call):
                    fn = node.func
                    fname = getattr(fn, "attr", None) or getattr(fn, "id", "")
                    # 形态① os.getenv("DEMO_VETO")；形态② os.environ.get("DEMO_VETO")
                    is_environ_get = (
                        fname == "get"
                        and isinstance(fn, _ast.Attribute)
                        and _is_environ(fn.value)
                    )
                    if fname == "getenv" or is_environ_get:
                        for arg in (*node.args, *node.keywords):
                            val = arg.value if isinstance(arg, _ast.keyword) else arg
                            if isinstance(val, _ast.Constant) and isinstance(val.value, str):
                                if "demo_veto" in val.value.lower().replace("-", "_"):
                                    _flag(node.lineno, fname if fname == "getenv" else "environ.get")
                elif isinstance(node, _ast.Subscript):
                    # 形态③ os.environ["DEMO_VETO"]
                    if _is_environ(node.value) and isinstance(node.slice, _ast.Constant):
                        val = node.slice.value
                        if isinstance(val, str) and "demo_veto" in val.lower().replace("-", "_"):
                            _flag(node.lineno, "environ[...]")
    # 2) 配置 YAML 不得出现 demo_veto 键
    for rel in ("core-rule/config", "app-zeri"):
        root = repo_root / rel
        if not root.exists():
            continue
        for path in root.rglob("*.yaml"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.split("#", 1)[0]
                if "demo_veto" in stripped and ":" in stripped:
                    rel_path = path.relative_to(repo_root)
                    problems.append(
                        f"{rel_path}:{i}: 配置文件不得携带 demo_veto 键"
                        "（开关只在 CLI 参数与测试代码里）"
                    )
    return problems
