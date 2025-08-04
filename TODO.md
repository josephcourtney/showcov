* [x] replace path filtering logic with `pathspec`
  * [x] Convert glob-style includes/excludes to `pathspec.PathSpec`.
  * [x] Resolve real paths to normalize matching behavior.
* [x] Use `more-itertools.consecutive_groups` for consecutive group merging
  * [x] Wrap `consecutive_groups` in a `list(list(...))` to normalize output format.
  * [x] Retain `merge_blank_gap_groups`—there’s no drop-in replacement.
* [x] update the feature list in the README.md
