* replace path filtering logic with `pathspec`
  * Convert glob-style includes/excludes to `pathspec.PathSpec`.
  * Resolve real paths to normalize matching behavior.
* Use `more-itertools.consecutive_groups` for consecutive group merging
  * Wrap `consecutive_groups` in a `list(list(...))` to normalize output format.
  * Retain `merge_blank_gap_groups`—there’s no drop-in replacement.
* update the feature list in the README.md
