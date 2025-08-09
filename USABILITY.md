# Usability Review of Showcov

## Overview
Showcov is a CLI tool for inspecting uncovered lines reported by Python coverage. This review summarizes successful behaviors and usability issues observed while exercising the CLI and its subcommands.

## Successes
- **Automatic coverage file resolution** – when no `--cov` path is supplied, the tool locates `.coverage.xml` based on project configuration and proceeds normally【0be106†L1-L4】
- **Rich output formats** – uncovered sections can be rendered as human-readable tables, JSON, Markdown, SARIF, or HTML, enabling both human and machine consumption【5d0700†L1-L52】【9d810c†L1-L10】【20d233†L1-L10】【3c7ec4†L1-L9】【a4b1a8†L1-L10】
- **Include/exclude filtering** – file selection works when explicit paths are provided, allowing focused reports on specific modules【11e579†L1-L17】【eca7a7†L1-L42】
- **Statistics options** – `--file-stats` and `--stats` append per-file and aggregate counts to the human format, helping judge coverage at a glance【55bf2b†L61-L70】【b8245f†L1-L58】
- **Diff subcommand** – comparing two coverage reports highlights resolved sections in both human and JSON formats【8c7e5b†L1-L8】【aa14bb†L1-L10】

## Problems and Suggestions
- **Documented flags missing** – options advertised in the README such as `--interactive`, `--summary-only`, and `--list-files` are rejected by the CLI. Provide these features or remove them from documentation to avoid confusion【4d9915†L1-L5】【b1fc4e†L1-L5】【8433d5†L1-L5】
- **Path controls incomplete** – `--no-paths` has no effect and `--include`/`--exclude` patterns behave inconsistently (e.g., `--include src/showcov/*` matches nothing while `--exclude` fails to omit core files). Implement proper path filtering and honour `--no-paths` to suppress file columns【d5c7a8†L1-L2】【98b3fc†L1-L50】【553f6a†L1-L57】
- **Line-number flag unused** – line numbers are always printed in code snippets even without `--line-numbers`, suggesting the flag is ignored. Either remove the option or wire it to the renderer to allow hiding numbers【db6d37†L1-L20】【79641a†L1-L10】
- **Context parsing crash** – non-numeric `--context` values raise a raw traceback instead of a helpful message. Validate input and report errors via Click’s `BadParameter`【80d7a9†L1-L24】
- **`--no-code` ignored in Markdown** – code blocks still appear when `--no-code` is requested. Ensure the option suppresses source snippets across all formats【936a89†L1-L10】
- **JSON lacks statistics** – `--stats` and `--file-stats` do not add any summary fields to JSON output, reducing its usefulness for automation. Embed totals and per-file counts in the JSON schema【526623†L1-L20】【72a202†L1-L20】
- **Unfriendly errors on output path issues** – specifying a directory or nonexistent parent for `--output` triggers Python exceptions rather than user-friendly messages. Catch filesystem errors and surface clear guidance【4fa744†L1-L31】【c2a300†L1-L31】
- **Verbose mode silent** – `--verbose` produces the same output as the default run, offering no additional diagnostics. Emit extra logging when verbosity is enabled to aid troubleshooting【63ef8e†L1-L2】【56c85e†L1-L58】
- **No format suggestion** – mistyped formats result in a simple error, contrary to the README’s promise of suggestions. Provide fuzzy suggestions for `--format` typos【1cd571†L1-L5】
- **Auto format ignores `--output` target** – `--format auto` writes human output when saving to a file because detection relies solely on `stdout.isatty`. Consider switching to JSON when `--output` is set or require explicit format selection for files【10c7d4†L1-L11】
- **Diff lacks pager controls** – unlike `show`, the `diff` subcommand has no `--no-pager` option, forcing manual paging for large reports. Add pager flags for consistency【497b57†L1-L4】
- **Auto-pager surprises** – long reports page by default, requiring a manual quit (`q`) to exit. Document this prominently or disable auto-paging unless explicitly requested to avoid trapping users in pagers【78791f†L1-L21】

## Conclusion
Showcov offers powerful coverage inspection features, but several flags are undocumented or non-functional, and error handling could be more user-friendly. Addressing these issues would make the tool more approachable for new users and more predictable for experienced developers.
