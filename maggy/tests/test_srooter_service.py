"""Tests for the srooter enablement service (wraps `srooterctl`)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from maggy.services import srooter

DOCTOR_ON = """srooter doctor — https://api.srooter.ai
  config           : OK (key …ab12, /home/u/.srooter/config)
  claude routing   : OK (settings.json env → srooter)
  heartbeat hook   : OK (Stop hook installed)
  cortex auto-index: OK (SessionStart hook — every project, same key)
  shell routing    : OK (active.env — new terminals + Codex/OpenAI tools)
  gateway probe    : OK (200, key valid)
"""

DOCTOR_OFF = """srooter doctor — https://api.srooter.ai
  config           : FAIL (no key — run: srooterctl init <key> [url])
  claude routing   : FAIL (settings.json not wired — run: srooterctl claude-env on) [got=<none>]
  heartbeat hook   : FAIL (run: srooterctl heartbeat-hook on)
  cortex auto-index: off (run: srooterctl cortex-hook on)
  shell routing    : off (optional — run: srooterctl enable)
  gateway probe    : skip (no key)
"""


class TestParseDoctor:
    def test_enabled_state(self):
        s = srooter._parse_doctor(DOCTOR_ON)
        assert s["installed"] is True
        assert s["enabled"] is True
        assert s["key_set"] is True
        assert s["shell_routing"] is True
        assert s["gateway"] == "https://api.srooter.ai"

    def test_disabled_state(self):
        s = srooter._parse_doctor(DOCTOR_OFF)
        assert s["enabled"] is False
        assert s["key_set"] is False
        assert s["shell_routing"] is False


class TestStatus:
    @patch("maggy.services.srooter.find_srooterctl", return_value=None)
    def test_not_installed(self, _missing):
        s = srooter.status()
        assert s["installed"] is False
        assert s["enabled"] is False
        assert "hint" in s

    @patch("maggy.services.srooter._run")
    @patch("maggy.services.srooter.find_srooterctl", return_value="/bin/srooterctl")
    def test_installed_parses_doctor(self, _ctl, mock_run):
        mock_run.return_value = MagicMock(stdout=DOCTOR_ON, returncode=0)
        s = srooter.status()
        assert s["enabled"] is True
        mock_run.assert_called_once_with(["doctor"])


class TestEnable:
    @patch("maggy.services.srooter._run")
    @patch("maggy.services.srooter.find_srooterctl", return_value="/bin/srooterctl")
    def test_runs_repair_with_key(self, _ctl, mock_run):
        mock_run.return_value = MagicMock(stdout=DOCTOR_ON, returncode=0)
        srooter.enable("srt_abc12345")
        assert mock_run.call_args_list[0].args[0] == ["repair", "srt_abc12345"]

    @patch("maggy.services.srooter._run")
    @patch("maggy.services.srooter.find_srooterctl", return_value="/bin/srooterctl")
    def test_passes_gateway_url(self, _ctl, mock_run):
        mock_run.return_value = MagicMock(stdout=DOCTOR_ON, returncode=0)
        srooter.enable("srt_abc12345", "http://127.0.0.1:8799")
        assert mock_run.call_args_list[0].args[0] == [
            "repair", "srt_abc12345", "http://127.0.0.1:8799",
        ]

    @patch("maggy.services.srooter.status", return_value={"key_set": False})
    def test_rejects_empty_key_when_none_saved(self, _s):
        with pytest.raises(ValueError):
            srooter.enable("   ")

    @patch("maggy.services.srooter._run")
    @patch("maggy.services.srooter.status", return_value={"key_set": True, "enabled": True})
    def test_empty_key_reuses_saved_config(self, _s, mock_run):
        srooter.enable("")
        assert mock_run.call_args_list[0].args[0] == ["repair"]

    def test_rejects_key_with_shell_metachars(self):
        with pytest.raises(ValueError):
            srooter.enable("srt_abc; rm -rf /")

    def test_rejects_leading_hyphen_key(self):
        # argv flag smuggling: a key like "-x" must never reach srooterctl
        with pytest.raises(ValueError):
            srooter.enable("--help")

    @patch("maggy.services.srooter._run")
    @patch("maggy.services.srooter.find_srooterctl", return_value="/bin/srooterctl")
    def test_rejects_bad_gateway_url(self, _ctl, _run):
        with pytest.raises(ValueError):
            srooter.enable("srt_abc12345", "file:///etc/passwd")


class TestDisable:
    @patch("maggy.services.srooter._run")
    @patch("maggy.services.srooter.find_srooterctl", return_value="/bin/srooterctl")
    def test_runs_claude_env_off_and_disable(self, _ctl, mock_run):
        mock_run.return_value = MagicMock(stdout=DOCTOR_OFF, returncode=0)
        srooter.disable()
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert ["claude-env", "off"] in calls
        assert ["disable"] in calls
