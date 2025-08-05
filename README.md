# showcov

showcov is a command-line utility that prints uncovered lines of code—grouped into contiguous sections—from a coverage XML report.

## Paging

When running in a terminal, showcov will pipe output through a pager by default. Use `--no-pager` or set the environment
variable `SHOWCOV_PAGER=off` to disable this behaviour. To force paging even when output is redirected, pass `--pager`.
