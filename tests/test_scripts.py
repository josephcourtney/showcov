from showcov.scripts import build_completion_script, build_man_page


def test_build_man_page_mentions_subcommands() -> None:
    man = build_man_page()
    assert "showcov - unified coverage report generator" in man
    assert "report" in man
    assert "diff" in man
    assert "EXIT STATUS" in man


def test_build_completion_script_includes_report_flags() -> None:
    script = build_completion_script("bash")
    assert "--format" in script
    assert "--snippets" in script
    assert "--fail-under-stmt" in script
    assert "--sections" in script
