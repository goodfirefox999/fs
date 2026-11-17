"""A 级影印实物档案的 schema 与「agent 不得签名」约束。

档案本身不是新门禁，而是把「可追溯性」落到叶面：每条引文必须能指到
一个 archive.org 扫描件、一个 0 基叶次、一张可重算哈希的页面图。
本测试守四件事：

1. 结构完整、URL 与叶次自洽、哈希格式正确；
2. ``verified_by`` 必须为空——AI 只能填 ``agent_checked_by``，不能代签；
3. 证据链闭合：所有 ``grade: A`` 且 ``quote_verified: true`` 的规则，
   必须至少有一条 primary 实物档案；``quote_verified: false`` 的 A 级规则
   必须出现在 gaps 里，不能既没叶面也没缺口登记；
4. ``correction_log`` 只增不改：已经写入的条目不得被后续 commit 静默修改或删除。

第 4 条依赖 git 历史：档案尚未纳入版本控制时只能 skip（skip 不算 pass，
gate 会以 exit 4 标记 undetermined）；纳入后本测试自动生效。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml
from core_rule.loader import load_ruleset

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "core-rule/config/citation_archive.yaml"
ARCHIVE_REL = "core-rule/config/citation_archive.yaml"
RULES_ROOT = ROOT / "core-rule/rules"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@pytest.fixture(scope="module")
def archive() -> dict:
    return yaml.safe_load(ARCHIVE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rule_ids() -> set[str]:
    return set(load_ruleset(RULES_ROOT).rule_ids)


def _rule_evidence() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(RULES_ROOT.rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rule_id = data.get("id") or data.get("rule_id")
        if rule_id and data.get("evidence"):
            out[rule_id] = data["evidence"]
    return out


class TestArchiveSchema:
    def test_top_level_shape(self, archive: dict) -> None:
        assert archive["schema_version"] == 1
        assert date.fromisoformat(archive["updated_at"])
        assert archive["edition"]["book"] == "欽定協紀辨方書"
        assert archive["policy"]["agent_must_not_sign"] is True

    def test_entry_ids_unique(self, archive: dict) -> None:
        ids = [entry["id"] for entry in archive["entries"]]
        assert len(ids) == len(set(ids))
        gap_ids = [gap["id"] for gap in archive["gaps"]]
        assert len(gap_ids) == len(set(gap_ids))

    def test_entry_required_fields(self, archive: dict) -> None:
        required = {
            "id",
            "rule_ids",
            "relation",
            "juan",
            "pian",
            "archive_item",
            "leaf",
            "page_url",
            "viewer_url",
            "image_sha256",
            "quote_kind",
            "quote_verbatim",
            "quote_scope",
            "quote_confidence",
            "uncertain_glyphs",
            "agent_checked_by",
            "agent_checked_at",
            "verified_by",
            "verified_at",
            "status",
            "notes",
        }
        for entry in archive["entries"]:
            missing = required - entry.keys()
            assert not missing, f"{entry['id']} 缺字段：{sorted(missing)}"

    def test_page_url_matches_item_and_leaf(self, archive: dict) -> None:
        for entry in archive["entries"]:
            item, leaf = entry["archive_item"], entry["leaf"]
            assert f"/{item}/page/n{leaf}.jpg" in entry["page_url"], entry["id"]
            assert entry["viewer_url"].endswith(f"/{item}#page/n{leaf}"), entry["id"]
            assert isinstance(leaf, int) and leaf >= 0, entry["id"]

    def test_image_hash_format(self, archive: dict) -> None:
        for entry in archive["entries"]:
            assert _SHA256.fullmatch(entry["image_sha256"]), entry["id"]

    def test_quote_confidence_and_scope(self, archive: dict) -> None:
        for entry in archive["entries"]:
            assert entry["quote_confidence"] in {"高", "中", "低"}, entry["id"]
            assert entry["quote_scope"] in {"全文", "节选"}, entry["id"]
            assert entry["quote_verbatim"].strip(), entry["id"]
            assert isinstance(entry["uncertain_glyphs"], list), entry["id"]
            if entry["quote_confidence"] != "高":
                assert entry["uncertain_glyphs"], f"{entry['id']} 标了非高置信却未列存疑字"

    def test_relation_and_status(self, archive: dict) -> None:
        allowed_status = set(archive["policy"]["status_values"])
        for entry in archive["entries"]:
            assert entry["relation"] in {"primary", "supplementary"}, entry["id"]
            assert entry["status"] in allowed_status, entry["id"]


class TestCorrectionLog:
    """已纠正的事实必须留痕，防止下一轮重新发现、重新写错。"""

    def test_required_corrections_present(self, archive: dict) -> None:
        log = archive.get("correction_log")
        assert isinstance(log, list), "缺 correction_log"
        ids = {entry["id"] for entry in log}
        assert {"CORR-001", "CORR-002", "CORR-003"} <= ids

    def test_entries_have_prior_actual_basis(self, archive: dict) -> None:
        for entry in archive["correction_log"]:
            assert entry["subject"].strip(), entry["id"]
            assert entry["prior_belief"].strip(), entry["id"]
            assert entry["actual"].strip(), entry["id"]
            assert entry["basis"].strip(), entry["id"]
            assert _ISO_DATE.fullmatch(entry["corrected_at"]), entry["id"]
            assert entry["status"] in {"closed", "open_pending_M4"}, entry["id"]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _correction_entries(raw_yaml: str) -> dict[str, str]:
    """把某次 commit 的 correction_log 归一为 {id: canonical(entry)}。"""
    data = yaml.safe_load(raw_yaml) or {}
    log = data.get("correction_log") or []
    return {entry["id"]: _canonical(entry) for entry in log}


class TestCorrectionLogImmutable:
    """correction_log 只能追加：旧条目不得被改写，也不得被删除。

    为什么用 git 历史而不是自哈希：自哈希可以连同哈希一起改，拦不住"静默修正"；
    git 历史是外部见证，能看到"上一版写了什么、这一版变成了什么"。
    """

    def test_history_is_append_only(self) -> None:
        if shutil.which("git") is None:
            pytest.skip("git 不可用，无法校验 correction_log 历史")
        tracked = _git("ls-files", "--error-unmatch", ARCHIVE_REL)
        if tracked.returncode != 0:
            pytest.skip(
                f"{ARCHIVE_REL} 尚未纳入 git（当前为未跟踪文件）；提交后本测试自动生效"
            )
        log = _git("log", "--format=%H", "--reverse", "--", ARCHIVE_REL)
        if log.returncode != 0:
            pytest.skip(f"git log 失败：{log.stderr.strip()}")
        revisions = [line for line in log.stdout.splitlines() if line.strip()]
        if len(revisions) < 2:
            pytest.skip("档案只有一个历史版本，尚无「修改」可校验")

        previous: dict[str, str] = {}
        previous_sha: str | None = None
        for rev in revisions:
            show = _git("show", f"{rev}:{ARCHIVE_REL}")
            assert show.returncode == 0, f"{rev} 无法读取档案：{show.stderr.strip()}"
            current = _correction_entries(show.stdout)
            current_sha = hashlib.sha256(
                _canonical(sorted(current.items())).encode("utf-8")
            ).hexdigest()

            for entry_id, fingerprint in previous.items():
                assert entry_id in current, (
                    f"{rev[:12]} 删除了 correction_log 条目 {entry_id}；"
                    "已纠正事实只能追加，不得静默删除"
                )
                assert current[entry_id] == fingerprint, (
                    f"{rev[:12]} 修改了 correction_log 条目 {entry_id}；"
                    "如需纠正请追加新条目并说明原条目作废"
                )

            # 用户口径的粗粒度兜底：内容变了但条目数没增，必然发生了改/删
            if previous_sha is not None and current_sha != previous_sha:
                assert len(current) > len(previous), (
                    f"{rev[:12]} correction_log 的 SHA 变了但条目数未增加"
                    f"（{len(previous)} → {len(current)}）"
                )

            previous = current
            previous_sha = current_sha


class TestAgentMustNotSign:
    def test_verified_by_is_null(self, archive: dict) -> None:
        for entry in archive["entries"]:
            assert entry["verified_by"] is None, f"{entry['id']} 出现签名：agent 不得代填 verified_by"
            assert entry["verified_at"] is None, entry["id"]

    def test_agent_checked_metadata_present(self, archive: dict) -> None:
        for entry in archive["entries"]:
            assert entry["agent_checked_by"], entry["id"]
            assert _ISO_DATE.fullmatch(entry["agent_checked_at"]), entry["id"]

    def test_pending_status_has_no_signature(self, archive: dict) -> None:
        for entry in archive["entries"]:
            if entry["status"] == "pending_human_countersign":
                assert entry["verified_by"] is None, entry["id"]


class TestEvidenceClosure:
    def test_rule_ids_exist(self, archive: dict, rule_ids: set[str]) -> None:
        for entry in archive["entries"]:
            unknown = set(entry["rule_ids"]) - rule_ids
            assert not unknown, f"{entry['id']} 引用了不存在的规则：{sorted(unknown)}"
        for gap in archive["gaps"]:
            unknown = set(gap["rule_ids"]) - rule_ids
            assert not unknown, f"{gap['id']} 引用了不存在的规则：{sorted(unknown)}"

    def test_a_grade_verified_rules_have_primary_archive(self, archive: dict) -> None:
        covered = {
            rule_id for entry in archive["entries"] if entry["relation"] == "primary" for rule_id in entry["rule_ids"]
        }
        missing = [
            rule_id
            for rule_id, ev in _rule_evidence().items()
            if ev.get("grade") == "A" and ev.get("quote_verified") is True and rule_id not in covered
        ]
        assert not missing, f"A 级已核对规则缺实物档案：{sorted(missing)}"

    def test_a_grade_unverified_rules_registered_as_gaps(self, archive: dict) -> None:
        gapped = {rule_id for gap in archive["gaps"] for rule_id in gap["rule_ids"]}
        missing = [
            rule_id
            for rule_id, ev in _rule_evidence().items()
            if ev.get("grade") == "A" and ev.get("quote_verified") is not True and rule_id not in gapped
        ]
        assert not missing, f"A 级未核对规则既无档案也未登记缺口：{sorted(missing)}"

    def test_every_gap_has_missing_items_and_next_step(self, archive: dict) -> None:
        for gap in archive["gaps"]:
            assert gap["missing"], gap["id"]
            assert gap["next_step"].strip(), gap["id"]
            assert gap["current_state"].strip(), gap["id"]

    def test_no_duplicate_leaf_for_same_item(self, archive: dict) -> None:
        seen: dict[tuple[str, int], str] = {}
        for entry in archive["entries"]:
            key = (entry["archive_item"], entry["leaf"])
            assert key not in seen, f"{entry['id']} 与 {seen[key]} 指向同一叶，应合并或说明差异"
            seen[key] = entry["id"]
