from showcov.core.config import LOG_FORMAT, get_schema
from showcov.core.core import (
    UncoveredSection,
    _get_xml_from_config,
    _get_xml_from_pyproject,
    build_sections,
    determine_xml_file,
    diff_uncovered_lines,
    gather_uncovered_lines,
    gather_uncovered_lines_from_xml,
    get_config_xml_file,
    group_consecutive_numbers,
    merge_blank_gap_groups,
    parse_large_xml,
)
from showcov.core.coverage import (
    FileAgg,
    LineAgg,
    compute_file_rows,
    find_coverage_xml_paths,
    iter_lines,
    parse_condition_coverage,
    read_all_coverage_roots,
)
from showcov.core.coverage import (
    aggregate as aggregate_coverage,
)
from showcov.core.coverage import (
    relativize as relativize_path,
)
from showcov.core.coverage import (
    sort_rows as sort_coverage_rows,
)
from showcov.core.dataset import (
    CoverageDataset,
    FileCoverage,
    LineCoverage,
    Report,
    build_branches,
    build_dataset,
    build_diff,
    build_lines,
    build_summary,
)
from showcov.core.exceptions import (
    CoverageXMLError,
    CoverageXMLNotFoundError,
    InvalidCoverageXMLError,
    ShowcovError,
)
from showcov.core.files import detect_line_tag, normalize_path, read_file_lines
from showcov.core.path_filter import PathFilter
from showcov.core.types import (
    BranchMode,
    CoveragePercent,
    FilePath,
    Format,
    LineRange,
    SummarySort,
)

__all__ = [
    "LOG_FORMAT",
    "BranchMode",
    "CoverageDataset",
    "CoveragePercent",
    "CoverageXMLError",
    "CoverageXMLNotFoundError",
    "FileAgg",
    "FileCoverage",
    "FilePath",
    "Format",
    "InvalidCoverageXMLError",
    "LineAgg",
    "LineCoverage",
    "LineRange",
    "PathFilter",
    "Report",
    "ShowcovError",
    "SummarySort",
    "UncoveredSection",
    "_get_xml_from_config",
    "_get_xml_from_pyproject",
    "aggregate_coverage",
    "build_branches",
    "build_dataset",
    "build_diff",
    "build_lines",
    "build_sections",
    "build_summary",
    "compute_file_rows",
    "detect_line_tag",
    "determine_xml_file",
    "diff_uncovered_lines",
    "find_coverage_xml_paths",
    "gather_uncovered_lines",
    "gather_uncovered_lines_from_xml",
    "get_config_xml_file",
    "get_schema",
    "group_consecutive_numbers",
    "iter_lines",
    "merge_blank_gap_groups",
    "normalize_path",
    "parse_condition_coverage",
    "parse_large_xml",
    "read_all_coverage_roots",
    "read_file_lines",
    "relativize_path",
    "sort_coverage_rows",
]
