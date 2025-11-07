from showcov.scripts import build_completion_script, build_man_page


def test_build_man_page_mentions_options() -> None:
    man = build_man_page()
    assert "showcov - unified coverage report generator" in man
    assert "--sections" in man
    assert "EXIT STATUS" in man
    assert "2  coverage threshold failure" in man


def test_build_completion_script_lists_new_options() -> None:
    script = build_completion_script("bash")
    assert "--sections" in script
    assert "--branches-mode" in script
    assert "--threshold" in script
