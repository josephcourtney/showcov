from __future__ import annotations

from .types import BuildOptions
from showcov.model.report import (
    EnvironmentMeta,
    LinesSection,
    OptionsMeta,
    Report,
    ReportMeta,
    ReportSections,
)
from .lines import _build_lines_section
from .branches import _build_branches_section
from .summary import _build_summary_section

def build_report(opts: BuildOptions) -> Report:
    # Meta per schema
    meta = ReportMeta(
        environment=EnvironmentMeta(coverage_xml=", ".join(str(p) for p in opts.coverage_paths)),
        options=OptionsMeta(
            context_lines=max(opts.context_before, opts.context_after),
            with_code=bool(opts.want_snippets),
            show_paths=bool(opts.meta_show_paths),
            show_line_numbers=bool(opts.meta_show_line_numbers),
            aggregate_stats=bool(opts.want_aggregate_stats),
            file_stats=bool(opts.want_file_stats),
        ),
    )

    # Lines (built only when needed: lines)
    lines: LinesSection | None = (
        _build_lines_section(
            records=opts.records,
            base=opts.base_path,
            filters=opts.filters,
            want_aggregate_stats=opts.want_aggregate_stats,
            want_file_stats=opts.want_file_stats,
        )
        if ("lines" in opts.sections)
        else None
    )

    # Branches
    branches = (
        _build_branches_section(
            opts.records,
            base=opts.base_path,
            filters=opts.filters,
            mode=opts.branches_mode,
        )
        if "branches" in opts.sections
        else None
    )

    # Assemble present sections only
    sections = ReportSections(
        lines=lines,
        branches=branches,
        summary=(
            _build_summary_section(
                opts.records,
                base=opts.base_path,
                filters=opts.filters,
                sort=opts.summary_sort,
            )
            if "summary" in opts.sections
            else None
        ),
    )

    return Report(meta=meta, sections=sections)
