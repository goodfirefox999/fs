"""确定性门禁适配层的三态处置（2026-11-04 第五层改写）。

探针本身返回 0/1/2/3；适配层按三态翻译：
- 0 → 0（通过）
- 1 → 1（PRODUCT_FAIL，阻断）
- 2/3/未知码 → 4（undetermined，不是通过；3 另写 ``out/output-fail.flag``）
本文件锁住四件事：3→4 且留 flag；0 清理旧 flag；1 原样阻断；2/未知码→4。
每个用例都配反证：该留 flag 时文件必须在，该阻断时文件必须不在。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "determinism_gate", Path(__file__).resolve().parents[2] / "tools" / "determinism_gate.py"
)
assert _SPEC and _SPEC.loader
gate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gate)


class TestArbitrate:
    def test_output_fail_is_undetermined_but_flagged(self, tmp_path: Path, capsys) -> None:
        rc = gate.arbitrate(
            3,
            "decision=aaa\noutput=bbb\n",
            "OUTPUT_FAIL（输出面）: 决策一致，但报告文本跨进程不稳定",
            tmp_path,
        )
        assert rc == 4, "OUTPUT_FAIL 是「无法判定」，不得再降级为通过"
        flag = tmp_path / gate.FLAG_NAME
        assert flag.exists(), "无法判定必须留下机器可查的证据"
        payload = json.loads(flag.read_text(encoding="utf-8"))
        assert payload["kind"] == "OUTPUT_FAIL"
        assert payload["probe_rc"] == 3
        assert payload["disposition"] == "undetermined"
        assert "OUTPUT_FAIL" in payload["probe_stderr"]
        err = capsys.readouterr().err
        assert "UNDETERMINED" in err and "不是全绿" in err

    def test_success_clears_stale_flag(self, tmp_path: Path, capsys) -> None:
        flag = tmp_path / gate.FLAG_NAME
        flag.write_text('{"kind": "OUTPUT_FAIL"}', encoding="utf-8")
        assert gate.arbitrate(0, "DETERMINISTIC: decision=aaa output=bbb", "", tmp_path) == 0
        assert not flag.exists(), "本次成功必须清掉上一次的警告，否则告警会永久粘住"
        assert "DETERMINISTIC" in capsys.readouterr().out

    def test_product_fail_blocks(self, tmp_path: Path) -> None:
        assert gate.arbitrate(1, "", "决策不一致", tmp_path) == 1
        assert not (tmp_path / gate.FLAG_NAME).exists(), "阻断不得被伪装成无法判定"

    def test_env_suspect_is_undetermined(self, tmp_path: Path, capsys) -> None:
        assert gate.arbitrate(2, "", "机器忙", tmp_path) == 4
        assert not (tmp_path / gate.FLAG_NAME).exists()
        assert "ENV_SUSPECT" in capsys.readouterr().err

    def test_unknown_code_is_undetermined(self, tmp_path: Path) -> None:
        assert gate.arbitrate(99, "", "", tmp_path) == 4
        assert not (tmp_path / gate.FLAG_NAME).exists()

    def test_probe_timeout_clears_stale_flag(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """探针超时时也不能让上一次的 OUTPUT_FAIL 残留。"""
        import subprocess

        flag = tmp_path / gate.FLAG_NAME
        flag.write_text('{"kind": "OUTPUT_FAIL"}', encoding="utf-8")

        def fake_run(cmd, **kwargs):  # noqa: ANN001
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1))

        monkeypatch.setattr(gate.subprocess, "run", fake_run)
        assert gate.main(["--out-dir", str(tmp_path)]) == 4
        assert not flag.exists()
        assert "超时" in capsys.readouterr().err


class TestAdapterEnv:
    def test_probe_subprocess_gets_adapter_token(self, monkeypatch, tmp_path: Path) -> None:
        """适配层必须显式放行探针的 CI 防绕过检查。"""
        seen: dict[str, object] = {}

        class Proc:
            returncode = 0
            stdout = "DETERMINISTIC: decision=aaa output=bbb"
            stderr = ""

        def fake_run(cmd, **kwargs):  # noqa: ANN001
            seen.update(kwargs)
            return Proc()

        monkeypatch.setattr(gate.subprocess, "run", fake_run)
        assert gate.main(["--out-dir", str(tmp_path)]) == 0
        assert seen["env"][gate.ADAPTER_ENV] == "1"


class TestRealProbe:
    def test_two_seeds_pass_without_flag(self, tmp_path: Path) -> None:
        """真实探针跑两个 seed：全绿时不得产生 flag。"""
        assert gate.main(["--seeds", "0,1", "--out-dir", str(tmp_path)]) == 0
        assert not (tmp_path / gate.FLAG_NAME).exists()
