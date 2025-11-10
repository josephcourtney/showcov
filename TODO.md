- [ ] ensure per-file line stats only render when `--file-stats` is set:
  - [ ] in `output.report_render._summarize_line_sections()`, print per-file lines only if `counts` exists **and** `report.meta["options"]["file_stats"]` is true; otherwise skip.
  - [ ] avoid defaulting to zeros when `counts` is absent.

- [ ] ensure aggregate uncovered count only renders when `--stats` is set:
  - [ ] in `_summarize_line_sections()`, print “Total uncovered lines: …” only if `report.meta["options"]["aggregate_stats"]` is true **and** a `summary.uncovered` value exists.

- [ ] make "human" printout more compact by separating table listing uncovered lines  by file so that the path does not need to be repeated

- [ ] improve code printout by mimicking ripgrep output:

