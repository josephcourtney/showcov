## TODO

- [x] fix `--color` flag so ANSI styling is preserved even when stdout is not a TTY (adjust Rich console usage in `format_human` and related formatters)
- [x] expose a functional `showcov completions` subcommand that emits scripts referencing the actual `showcov` executable instead of `grobl`
- [x] update the empty-state message in `render_output` to accurately describe the “fully covered” scenario instead of implying include-pattern mismatches
