"""Tests for MCP Forge connector, registry, and gap detection."""

from __future__ import annotations

from pathlib import Path

from maggy.forge.connector import ForgeConnector
from maggy.forge.detector import GapDetector, TRIGGER_THRESHOLD
from maggy.forge.registry import ForgeRegistry, ToolInfo


class TestForgeRegistry:
    def test_empty_without_forge(self):
        reg = ForgeRegistry(forge_path=None)
        assert reg.count == 0

    def test_loads_from_forge_path(self):
        forge = Path.home() / "Documents" / "protaige" / "mcp-forge"
        if not forge.exists():
            return  # skip if forge not available
        reg = ForgeRegistry(forge_path=forge)
        assert reg.count > 0

    def test_search(self):
        forge = Path.home() / "Documents" / "protaige" / "mcp-forge"
        if not forge.exists():
            return
        reg = ForgeRegistry(forge_path=forge)
        results = reg.search("stripe")
        assert any(t.slug == "stripe" for t in results)

    def test_get_missing(self):
        reg = ForgeRegistry(forge_path=None)
        assert reg.get("nonexistent") is None

    def test_set_enabled(self):
        reg = ForgeRegistry(forge_path=None)
        reg._tools["test"] = ToolInfo(slug="test")
        assert reg.set_enabled("test", False)
        assert not reg._tools["test"].enabled
        assert not reg.set_enabled("nope", False)


class TestGapDetector:
    def test_first_record_no_trigger(self):
        det = GapDetector()
        assert not det.record_gap("email sending")

    def test_trigger_at_threshold(self):
        det = GapDetector(threshold=3)
        det.record_gap("email sending")
        det.record_gap("email sending")
        assert det.record_gap("email sending")

    def test_no_double_trigger(self):
        det = GapDetector(threshold=2)
        det.record_gap("x")
        det.record_gap("x")  # triggers
        assert not det.record_gap("x")  # no re-trigger

    def test_list_gaps(self):
        det = GapDetector()
        det.record_gap("email")
        det.record_gap("email")
        det.record_gap("sms")
        gaps = det.list_gaps()
        assert len(gaps) == 2
        assert gaps[0].capability == "email"
        assert gaps[0].occurrences == 2

    def test_reset(self):
        det = GapDetector()
        det.record_gap("x")
        det.record_gap("x")
        det.reset("x")
        gaps = det.list_gaps()
        assert len(gaps) == 0


class TestForgeConnector:
    def test_status(self):
        conn = ForgeConnector(forge_path=Path("/nonexistent"))
        s = conn.status()
        assert not s.available
        assert s.registry_count == 0

    def test_report_gap(self):
        conn = ForgeConnector(forge_path=Path("/nonexistent"))
        r1 = conn.report_gap("payment processing")
        assert not r1["triggered"]

    def test_search_tools_empty(self):
        conn = ForgeConnector(forge_path=Path("/nonexistent"))
        assert conn.search_tools("stripe") == []

    def test_with_real_forge(self):
        forge = Path.home() / "Documents" / "protaige" / "mcp-forge"
        if not forge.exists():
            return
        conn = ForgeConnector(forge_path=forge)
        assert conn.available
        assert conn.status().registry_count > 0
        results = conn.search_tools("github")
        assert len(results) > 0
