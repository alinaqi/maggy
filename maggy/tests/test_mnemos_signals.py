"""Tests for JSONL signal logger."""

from datetime import datetime, timezone

from maggy.mnemos.signals import (
    ToolSignal,
    append_signal,
    count_signals_by_tool,
    extract_file_paths,
    read_recent_signals,
    read_signals,
    read_signals_since,
    signal_from_hook_data,
)


def _sig(tool: str = "Read", path: str = "a.py") -> ToolSignal:
    return ToolSignal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool_name=tool,
        file_path=path,
    )


class TestAppendAndRead:
    def test_roundtrip(self, tmp_mnemos_dir):
        s = _sig()
        append_signal(tmp_mnemos_dir, s)
        result = read_signals(tmp_mnemos_dir)
        assert len(result) == 1
        assert result[0].tool_name == "Read"

    def test_read_empty(self, tmp_mnemos_dir):
        assert read_signals(tmp_mnemos_dir) == []

    def test_multiple_signals(self, tmp_mnemos_dir):
        for i in range(5):
            append_signal(tmp_mnemos_dir, _sig(path=f"f{i}.py"))
        assert len(read_signals(tmp_mnemos_dir)) == 5


class TestReadRecent:
    def test_returns_last_n(self, tmp_mnemos_dir):
        for i in range(10):
            append_signal(tmp_mnemos_dir, _sig(path=f"f{i}.py"))
        recent = read_recent_signals(tmp_mnemos_dir, n=3)
        assert len(recent) == 3
        assert recent[0].file_path == "f7.py"
        assert recent[2].file_path == "f9.py"

    def test_empty_file(self, tmp_mnemos_dir):
        assert read_recent_signals(tmp_mnemos_dir, n=5) == []

    def test_n_larger_than_file(self, tmp_mnemos_dir):
        append_signal(tmp_mnemos_dir, _sig())
        assert len(read_recent_signals(tmp_mnemos_dir, n=100)) == 1

    def test_zero_n(self, tmp_mnemos_dir):
        append_signal(tmp_mnemos_dir, _sig())
        assert read_recent_signals(tmp_mnemos_dir, n=0) == []

    def test_skips_malformed_lines(self, tmp_mnemos_dir):
        from maggy.mnemos.constants import SIGNALS_FILENAME
        path = tmp_mnemos_dir / SIGNALS_FILENAME
        append_signal(tmp_mnemos_dir, _sig(path="good.py"))
        with path.open("a") as f:
            f.write("NOT VALID JSON\n")
        append_signal(tmp_mnemos_dir, _sig(path="also_good.py"))
        recent = read_recent_signals(tmp_mnemos_dir, n=3)
        assert len(recent) == 2
        assert recent[0].file_path == "good.py"
        assert recent[1].file_path == "also_good.py"


class TestReadSince:
    def test_filters_old(self, tmp_mnemos_dir):
        s = _sig()
        append_signal(tmp_mnemos_dir, s)
        future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        assert read_signals_since(tmp_mnemos_dir, future) == []


class TestAggregations:
    def test_count_by_tool(self):
        signals = [_sig("Read"), _sig("Read"), _sig("Write")]
        counts = count_signals_by_tool(signals)
        assert counts["Read"] == 2
        assert counts["Write"] == 1

    def test_extract_paths(self):
        signals = [_sig(path="a.py"), _sig(path="a.py"), _sig(path="b.py")]
        paths = extract_file_paths(signals)
        assert paths == ["a.py", "b.py"]


class TestFromHookData:
    def test_parses_hook_data(self):
        data = {"tool_name": "Edit", "file_path": "x.py"}
        sig = signal_from_hook_data(data)
        assert sig.tool_name == "Edit"
        assert sig.file_path == "x.py"

    def test_defaults(self):
        sig = signal_from_hook_data({})
        assert sig.tool_name == "unknown"
