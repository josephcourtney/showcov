from showcov.entrypoints.cli import cli
from showcov.entrypoints.cli.completion import build_completion_script
from showcov.entrypoints.cli.man import build_man_page


def test_build_man_page_mentions_subcommands() -> None:
    man = build_man_page(cli)
    assert "showcov - unified coverage report generator" in man
    assert "report" in man
    assert "EXIT STATUS" in man


def test_build_completion_script_includes_report_flags() -> None:
    script = build_completion_script("bash", command=cli)
    assert "--lines" in script
    assert "--branches" in script
    assert "--summary" in script
    assert "--code" in script
    assert "--context" in script
    assert "--fail-under-stmt" in script
    assert "--max-depth" in script
