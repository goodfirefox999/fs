"""确定性门禁适配层的退出码处置（2026-11-03 评审七回路）。

探针本身返回 0/1/2/3；适配层只允许把 3 降级成 0，并留下可机查的 flag。
本文件锁住四件事：

- 3 → 0 + ``out/output-fail.flag``（带警告通过，不能无声）
- 0 → 0 + **清理旧 flag**（否则上一次的警告会贴到这一次）
- 1/2 → 原样阻断（产品坏 / 机器忙都不能被吞）
- 未知退出码 → 2（门禁自身异常，先查调用方式）

每个用例都配反证：该留 flag 时文件必须在，该阻断时文件必须不在。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "determinism_gate", Path(__file__).resolve().parents[2] / "tools" / "determinism_gate.py"
)
assert _SPEC and _SPEC.loader
gate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gate)


class TestArbitrate:
    def test_output_fail_is_warning_but_flagged(self, tmp_path: Path, capsys) -> None:
        rc = gate.arbitrate(
            3,
            "decision=aaa\noutput=bbb\n",
            "OUTPUT_FAIL（输出面）: 决策一致，但报告文本跨进程不稳定",
            tmp_path,
        )
        assert rc == 0, "OUTPUT_FAIL 必须降级为带警告通过"
        flag = tmp_path / gate.FLAG_NAME
        assert flag.exists(), "降级必须留下机器可查的证据"
        payload = json.loads(flag.read_text(encoding="utf-8"))
        assert payload["kind"] == "OUTPUT_FAIL"
        assert payload["probe_rc"] == 3
        assert payload["disposition"] == "warn-and-pass"
        assert "OUTPUT_FAIL" in payload["probe_stderr"]
        err = capsys.readouterr().err
        assert "⚠️" in err and "不得当作全绿" in err

    def test_success_clears_stale_flag(self, tmp_path: Path, capsys) -> None:
        flag = tmp_path / gate.FLAG_NAME
        flag.write_text('{"kind": "OUTPUT_FAIL"}', encoding="utf-8")
        assert gate.arbitrate(0, "DETERMINISTIC: decision=aaa output=bbb", "", tmp_path) == 0
        assert not flag.exists(), "本次成功必须清掉上一次的警告，否则告警会永久粘住"
        assert "DETERMINISTIC" in capsys.readouterr().out

    @pytest.mark.parametrize("probe_rc", [1, 2])
    def test_blocking_codes_are_not_downgraded(self, tmp_path: Path, probe_rc: int) -> None:
        assert gate.arbitrate(probe_rc, "", "失败原因", tmp_path) == probe_rc
        assert not (tmp_path / gate.FLAG_NAME).exists(), "阻断不得被伪装成带警告通过"

    def test_unknown_code_is_env_suspect(self, tmp_path: Path) -> None:
        assert gate.arbitrate(99, "", "", tmp_path) == 2
        assert not (tmp_path / gate.FLAG_NAME).exists()

    def test_probe_timeout_clears_stale_flag(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """探针超时时也不能让上一次的 OUTPUT_FAIL 残留。"""
        import subprocess

        flag = tmp_path / gate.FLAG_NAME
        flag.write_text('{"kind": "OUTPUT_FAIL"}', encoding="utf-8")

        def fake_run(cmd, **kwargs):  # noqa: ANN001
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1))

        monkeypatch.setattr(gate.subprocess, "run", fake_run)
        assert gate.main(["--out-dir", str(tmp_path)]) == 2
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
