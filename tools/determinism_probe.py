"""确定性探针：证明「同输入必同输出」在**跨进程**下成立。

为什么需要它
------------
本项目对外承诺可复现（报告含 `input_hash`）。但 Python 的 `str` 哈希每个进程随机，
只要有一条代码路径让 `set` / `dict`（键为 str 且由集合构造）的**迭代顺序**参与决策
（取第一个、取最大值、拼字符串、选默认值），同一份输入在不同进程就可能给出不同结果。
这种 bug 在单进程测试里永远抓不到，只会在全量跑时表现为"偶发失败"。

用法
----
    python tools/determinism_probe.py              # 打印指纹
    python tools/determinism_probe.py --verbose    # 同时打印各段指纹

    for s in 0 1 2 3 4 5; do PYTHONHASHSEED=$s python tools/determinism_probe.py; done | sort -u

最后一条命令只应输出 **一行**。输出多行即表示存在跨进程不确定性，
用 `--verbose` 对比两行即可定位到是「事实层」还是「判定层」先漂。

设计约束
--------
- 只走公开入口（`build_context` / `evaluate`），不碰内部函数，避免探针自己成为耦合点。
- 序列化一律 `sort_keys=True`：我们要测的是**取值**是否稳定，不是序列化顺序。
- 不依赖当前时间、不联网、不写文件。

覆盖边界（2026-11-03 评审七回路）
--------------------------------
- **输出指纹只承诺「排序后的最终输出」**：`reasons` 与 `conflicts` 在进指纹前已
  `sorted`。因此绿 = 用户最终看到的文本稳定，**不**等于生成过程稳定。
- 中间态（未排序 reasons、未排序 conflicts、set/dict 迭代序）不在承诺范围内。
  若未来有接口直接暴露未排序列表，必须另加指纹（或先把排序点前移）。
- `fact_hash` / `input_hash` 仍不在两级指纹内（见 roadmap Q3）：它们是可复现清单
  字段，不是本次决策面/输出面的承诺。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

#: CI 中只有适配层可以调用 --gate。适配层会把它置为 "1"；直接调用会被拒绝。
#: 这不是安全边界，是防绕过：否则 3 会绕过 OUTPUT_FAIL 的「带警告通过」处置。
ADAPTER_ENV = "ZERI_DETERMINISM_ADAPTER"

for pkg in ("core-time", "core-symbol", "core-rule", "core-eval", "app-zeri"):
    src = ROOT / pkg / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TZ = ZoneInfo("Asia/Shanghai")

#: 覆盖「换年点 / 季节界 / 五黄宫 / 多时辰」这几类已知易错输入的固定日课
CASES: tuple[tuple[str, datetime, float], ...] = (
    ("金标准-2027-07-11", datetime(2027, 7, 11, 14, 0, tzinfo=TZ), 320.0),
    ("立春前-2027-01-15", datetime(2027, 1, 15, 10, 0, tzinfo=TZ), 320.0),
    ("立春后-2027-02-10", datetime(2027, 2, 10, 10, 0, tzinfo=TZ), 5.0),
    ("立冬后-2027-11-23", datetime(2027, 11, 23, 10, 0, tzinfo=TZ), 200.0),
    ("子时-2027-07-11", datetime(2027, 7, 11, 0, 30, tzinfo=TZ), 320.0),
)


def _canonical(obj: Any) -> str:
    """规范化 JSON。碰到 set/frozenset 直接报错——事实层不该出现无序容器。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=_no_default, separators=(",", ":"))


def _no_default(value: Any) -> Any:
    raise TypeError(f"facts 中出现不可规范化的类型 {type(value).__name__}：{value!r}")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _rid(item: Any) -> str:
    """兼容 Judgment 对象与 dict 两种形态（per_school.unknowns 与 ev.unknowns 不同型）。"""
    if isinstance(item, dict):
        return str(item.get("rule_id", ""))
    return str(getattr(item, "rule_id", ""))


def _eval_summary(ev: Any) -> dict[str, Any]:
    """只取判定结论与分层向量（不取时间戳/耗时等易变项）。"""
    per_school: dict[str, Any] = {}
    for school, res in sorted(getattr(ev, "per_school", {}).items()):
        per_school[school] = {
            "state": getattr(res, "state", None),
            "vetoes": sorted(_rid(j) for j in (getattr(res, "vetoes", []) or [])),
            "cautions": sorted(_rid(j) for j in (getattr(res, "cautions", []) or [])),
            "positives": sorted(_rid(j) for j in (getattr(res, "positives", []) or [])),
            "unknowns": sorted(_rid(j) for j in (getattr(res, "unknowns", []) or [])),
        }
    structural = sorted(_rid(j) for j in (getattr(ev, "structural", []) or []))
    return {
        "state": getattr(ev, "state", None),
        "tier": getattr(ev, "tier", None),
        "publishable": getattr(ev, "publishable", None),
        "vectors": getattr(ev, "vectors", None),
        "structural": structural,
        "per_school": per_school,
    }


def _judgment_text(j: Any) -> dict[str, Any]:
    """一条判定的**对外可读面**：结论 + 理由文本（排序后）。"""
    return {
        "rule_id": _rid(j),
        "verdict": getattr(j, "verdict", None),
        "severity": getattr(j, "severity", None),
        "reasons": sorted(str(x) for x in (getattr(j, "reasons", []) or [])),
    }


def _eval_output(ev: Any) -> dict[str, Any]:
    """只取**报告文本面**：reasons / conflicts / demo_hits / reference / rank_score。

    与 ``_eval_summary``（决策面）分开的理由（2026-11-03 评审七回路）：
    决策面一致但报告文本变，用户看到的是"同一个日课，两次查询给了不同解释"——
    这比 tier 翻更伤信任，因为用户无法判断哪个解释是真的。
    """
    per_school: dict[str, Any] = {}
    for school, res in sorted(getattr(ev, "per_school", {}).items()):
        buckets = (
            list(getattr(res, "vetoes", []) or [])
            + list(getattr(res, "cautions", []) or [])
            + list(getattr(res, "positives", []) or [])
            + list(getattr(res, "unknowns", []) or [])
            + list(getattr(res, "demo_hits", []) or [])
            + list(getattr(res, "reference", []) or [])
        )
        rank = getattr(res, "rank_score", None)
        per_school[school] = {
            # 浮点先 round 再哈希：避免末位抖动被当成"不确定"
            "rank_score": None if rank is None else round(float(rank), 6),
            "judgments": sorted(
                (_canonical(_judgment_text(j)) for j in buckets),
            ),
            "demo_hits": sorted(_rid(j) for j in (getattr(res, "demo_hits", []) or [])),
            "reference": sorted(_rid(j) for j in (getattr(res, "reference", []) or [])),
        }
    return {
        "conflicts": sorted(_canonical(c) for c in (getattr(ev, "conflicts", []) or [])),
        "per_school": per_school,
    }


def output_fingerprint(verbose: bool = False) -> dict[str, str]:
    """**输出指纹**（报告文本面）。与决策指纹分开存、分开断言。"""
    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
    from core_eval import EvalConfig, evaluate
    from core_rule import default_registry
    from core_time import CalendarConfig

    registry = default_registry()
    out: dict[str, str] = {}
    for name, dt, azimuth in CASES:
        ctx = build_context(
            course=CourseSpec(dt=dt),
            site=SiteSpec(azimuth_deg=azimuth, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            cal=CalendarConfig(),
        )
        ev = evaluate(
            ctx,
            registry,
            EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True, demo_veto=True),
        )
        out[f"{name}.output"] = _sha(_canonical(_eval_output(ev)))
    return out


def fingerprint(verbose: bool = False) -> dict[str, str]:
    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
    from core_eval import EvalConfig, evaluate
    from core_rule import default_registry
    from core_time import CalendarConfig

    registry = default_registry()
    out: dict[str, str] = {}
    for name, dt, azimuth in CASES:
        ctx = build_context(
            course=CourseSpec(dt=dt),
            site=SiteSpec(azimuth_deg=azimuth, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            cal=CalendarConfig(),
        )
        facts_sha = _sha(_canonical(ctx["facts"]))
        ev = evaluate(
            ctx,
            registry,
            EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True, demo_veto=True),
        )
        ev_sha = _sha(_canonical(_eval_summary(ev)))
        out[f"{name}.facts"] = facts_sha
        out[f"{name}.eval"] = ev_sha
    return out


def main(argv: list[str] | None = None) -> int:
    """命令行入口。退出码是**判据**，不是装饰：

    =====  ============================================================
    退出码  含义
    =====  ============================================================
    0      指纹一致（或本次单跑正常）
    1      **PRODUCT_FAIL**：跨 seed **决策指纹**不一致 —— 产品侧存在不确定性
    2      **ENV_SUSPECT**：耗时 > 基线中位数 2 倍 —— 先怀疑机器忙/进程争抢，
           **不得**据此判定产品不确定（见 AGENTS.md 补丁纪律第 7/8 条）
    3      **OUTPUT_FAIL**：决策一致但**输出指纹**不一致 —— 报告文本跨进程不稳定。
           可带警告发布，但不能无声（2026-11-03 评审七回路新增）
    64     **USAGE**：CI 中直接调用 --gate，绕过了 determinism_gate 适配层。
           这不是确定性判定，是调用方式错误；请改用 make gate。
    =====  ============================================================

    两级为什么分开：决策面红 = 产品坏了（必须停）；输出面红 = 用户看到的解释会变
    （比 tier 翻更伤信任，因为用户无法判断哪个解释是真的）。合并成一个指纹会把
    后者读成前者，也会把前者掩盖在"只是文本"里。

    为什么要把 1 和 2 分开：pytest 输出里超时与断言失败都显示为 ``FAILED``，
    不区分就会把"机器慢了"读成"算法坏了"——这正是 2026-11-02 那次误判的成因。
    """
    parser = argparse.ArgumentParser(description="跨进程确定性探针")
    parser.add_argument("--verbose", action="store_true", help="打印每一段的指纹")
    parser.add_argument("--fingerprint-only", action="store_true",
                        help="只打印两级指纹（供 --gate 子进程用）")
    parser.add_argument("--level", choices=("decision", "output", "both"), default="decision",
                        help="打印哪一级指纹：decision（决策面）/ output（报告文本面）/ both")
    parser.add_argument("--no-timing-check", action="store_true", help="跳过耗时基线检查（测试/低配机器用）")
    parser.add_argument(
        "--gate",
        nargs="?",
        const="0,1,2,3",
        default=None,
        metavar="SEEDS",
        help="一次性门禁：用多个 PYTHONHASHSEED 跑子进程并比对（默认 0,1,2,3）",
    )
    args = parser.parse_args(argv)

    if args.gate:
        # CI 中唯一入口是 tools/determinism_gate.py；绕过它会让 3 直接阻断，
        # 也会让「带警告通过」和「适配层坏了」无法区分。
        if os.environ.get("CI", "").lower() == "true" and os.environ.get(ADAPTER_ENV) != "1":
            print(
                "USAGE(64): CI 中禁止直接调用 determinism_probe.py --gate。\n"
                "  请改用 make gate（内部走 tools/determinism_gate.py），"
                "否则 OUTPUT_FAIL 会绕过适配层。",
                file=sys.stderr,
            )
            return 64
        return _gate(args.gate, verbose=args.verbose)

    t0 = time.perf_counter()
    parts = fingerprint(verbose=args.verbose and not args.fingerprint_only)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    total = _sha(_canonical(parts))
    out_parts = output_fingerprint(verbose=args.verbose and not args.fingerprint_only)
    out_total = _sha(_canonical(out_parts))
    if args.fingerprint_only:
        # 两行、两个标签：决策面与输出面**不合并**（合并会把"文本漂"读成"决策漂"）
        print(f"decision={total}")
        print(f"output={out_total}")
        return 0

    if args.level in ("decision", "both"):
        print("—— 决策面（state/tier/publishable/vectors/per_school 计数）——")
        for key, value in parts.items():
            print(f"{value}  {key}")
        print(f"decision={total}")
    if args.level in ("output", "both"):
        print("—— 输出面（reasons/conflicts/demo_hits/reference/rank_score）——")
        for key, value in out_parts.items():
            print(f"{value}  {key}")
        print(f"output={out_total}")

    if args.no_timing_check:
        return 0
    return _timing_check(elapsed_ms)


#: 耗时基线（滚动样本）。放在 out/ 下，已被 .gitignore 忽略。
BASELINE_PATH = ROOT / "out" / ".cache" / "determinism_baseline.json"
_BASELINE_SAMPLES = 20
_SUSPECT_FACTOR = 2.0


def _timing_check(elapsed_ms: float) -> int:
    """耗时 > 基线中位数 2 倍 → ENV_SUSPECT(2)，否则记录样本并返回 0。"""
    samples: list[float] = []
    if BASELINE_PATH.exists():
        try:
            data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
            samples = [float(x) for x in (data.get("samples_ms") or [])]
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            samples = []

    if samples:
        median = statistics.median(samples)
        if elapsed_ms > median * _SUSPECT_FACTOR:
            print(
                f"ENV_SUSPECT: 本次 {elapsed_ms:.0f} ms > 基线中位数 {median:.0f} ms × "
                f"{_SUSPECT_FACTOR:g}（阈值 {median * _SUSPECT_FACTOR:.0f} ms）。\n"
                "  这不代表产品不确定——先查：是否有并发 pytest / 扫描进程、机器是否在换页。\n"
                "  指纹本身若与其它 seed 一致，即产品侧确定。",
                file=sys.stderr,
            )
            return 2

    samples.append(round(elapsed_ms, 1))
    samples = samples[-_BASELINE_SAMPLES:]
    try:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps({"samples_ms": samples, "updated_at": datetime.now().isoformat(timespec="seconds")},
                       ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass  # 基线写不了不影响判定
    return 0


def _gate(seeds_csv: str, *, verbose: bool = False) -> int:
    """用多个 PYTHONHASHSEED 跑本文件的子进程，比对指纹。"""
    seeds = [s.strip() for s in seeds_csv.split(",") if s.strip()]
    if len(seeds) < 2:
        print("--gate 至少需要 2 个 seed", file=sys.stderr)
        return 1

    results: dict[str, dict[str, str]] = {}
    env_suspect = False
    slowest = 0.0
    for seed in seeds:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env.setdefault("PYTHONPATH", os.environ.get("PYTHONPATH", ""))
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--fingerprint-only"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(ROOT),
            timeout=300,
        )
        elapsed = time.perf_counter() - t0
        slowest = max(slowest, elapsed)
        if proc.returncode == 2:
            env_suspect = True
        if proc.returncode != 0:
            print(f"seed={seed} 子进程失败（rc={proc.returncode}）：\n{proc.stderr[-800:]}", file=sys.stderr)
            return 2
        pair: dict[str, str] = {}
        for line in proc.stdout.strip().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                pair[key.strip()] = value.strip()
        if "decision" not in pair or "output" not in pair:
            print(f"seed={seed} 子进程输出无法解析：{proc.stdout[-400:]!r}", file=sys.stderr)
            return 2
        results[seed] = pair

    if verbose:
        for seed, pair in results.items():
            print(f"seed={seed}  decision={pair['decision']}  output={pair['output']}")

    # ---- 两级分别断言，**不合并** ----
    decision_uniq = {p["decision"] for p in results.values()}
    output_uniq = {p["output"] for p in results.values()}

    if len(decision_uniq) > 1:
        print("PRODUCT_FAIL（决策面）: 不同 PYTHONHASHSEED 下 state/tier/vectors 不一致：",
              file=sys.stderr)
        for seed, pair in results.items():
            print(f"  seed={seed}  {pair['decision']}", file=sys.stderr)
        print("  这是产品坏了，必须停；取证用 --level both --verbose 看 facts/eval 哪段先漂。",
              file=sys.stderr)
        return 1

    if len(output_uniq) > 1:
        print("OUTPUT_FAIL（输出面）: 决策一致，但报告文本（reasons/conflicts/demo_hits/"
              "reference/rank_score）跨进程不稳定：", file=sys.stderr)
        for seed, pair in results.items():
            print(f"  seed={seed}  {pair['output']}", file=sys.stderr)
        print("  用户会看到「同一日课两次查询给了不同解释」。可带警告发布，但不能无声。",
              file=sys.stderr)
        return 3

    if env_suspect:
        return 2
    print(f"DETERMINISTIC: decision={next(iter(decision_uniq))} "
          f"output={next(iter(output_uniq))}（{len(seeds)} 个 seed 一致，最慢 {slowest:.1f}s）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
