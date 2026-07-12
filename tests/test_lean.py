from pathlib import Path

from crucible.lean import AMBIENT, DEFAULT_LEAN, LeanProfile


def test_ambient_adds_nothing():
    argv, cwd = AMBIENT.build()
    assert argv == [] and cwd is None and AMBIENT.name == "ambient"


def test_default_lean_disables_tools_and_settings():
    argv, cwd = DEFAULT_LEAN.build()
    # --tools "" is the primary lever; order: tools, strict-mcp, setting-sources
    assert argv == ["--tools", "", "--strict-mcp-config", "--setting-sources", ""]
    assert cwd is None and DEFAULT_LEAN.name == "tools-off"


def test_tools_empty_string_is_emitted_not_skipped():
    # "" is a real value (disable all tools); None means "don't pass the flag"
    argv, _ = LeanProfile(tools="").build()
    assert argv == ["--tools", ""]
    argv2, _ = LeanProfile(tools=None).build()
    assert "--tools" not in argv2


def test_setting_sources_empty_string_is_emitted_not_skipped():
    # "" is a real value (load no setting sources); None means "don't pass the flag"
    argv, _ = LeanProfile(setting_sources="").build()
    assert argv == ["--setting-sources", ""]
    argv2, _ = LeanProfile(setting_sources=None).build()
    assert "--setting-sources" not in argv2


def test_cwd_passthrough():
    _, cwd = LeanProfile(cwd=Path("/tmp/x")).build()
    assert cwd == "/tmp/x"
