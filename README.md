# showcov

showcov is a command-line utility that prints uncovered lines of code—grouped into contiguous sections—from a coverage XML report.

## Coverage summary

Run `showcov summary` to display the same compact statements/branches table that pytest prints in this repository. The command accepts path-based include/exclude filters and can sort by file name, statement coverage, branch coverage, or total misses.

## Branch analysis

Use `showcov branches` to inspect uncovered branch conditions. Pass `--code` (optionally with `--context` and `--line-numbers`) to see the surrounding source for each branch, which makes it easier to understand which path still needs a test.
