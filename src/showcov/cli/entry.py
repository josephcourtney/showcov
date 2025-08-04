"""Definition of the command line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
import click_completion
import click_completion.core
from defusedxml import ElementTree

from showcov import __version__
from showcov.cli.errors import (
    EXIT_DATAERR,
    EXIT_GENERIC,
    EXIT_NOINPUT,
    EXIT_OK,
)
from showcov.cli.util import (
    ShowcovOptions,
    _configure_runtime,
    _emit_manpage,
    determine_format,
    parse_flags_to_opts,
    render_output,
    resolve_sections,
    write_output,
)
from showcov.core import (
    CoverageXMLNotFoundError,
)

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence


# --------------------------------------------------------------------------- #
# CLI - root command group                                                    #
# --------------------------------------------------------------------------- #
@click.group(
    context_settings={
        "help_option_names": ["-h", "--help"],
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
    invoke_without_command=True,
)
@click.option(
    "--version",
    is_flag=True,
    is_eager=True,
    help="Show the version and exit",
)
@click.option("--debug", is_flag=True, help="Show full tracebacks for errors")
@click.option("-q", "--quiet", is_flag=True, help="Suppress INFO logs, emit only errors")
@click.option("-v", "--verbose", is_flag=True, help="Emit diagnostic logging")
@click.pass_context
def cli(ctx: click.Context, *, version: bool, debug: bool, quiet: bool, verbose: bool) -> None:
    """Showcov - show uncovered lines from a coverage XML report."""
    # initialise context storage
    ctx.obj = ShowcovOptions(debug=debug, quiet=quiet, verbose=verbose)

    # eager --version flag
    if version and ctx.invoked_subcommand is None:
        click.echo(__version__)
        ctx.exit(EXIT_OK)

    if ctx.invoked_subcommand is None:
        # no sub-command given → behave as if `show`
        ctx.forward(show)


# --------------------------------------------------------------------------- #
# Sub-command: version                                                        #
# --------------------------------------------------------------------------- #
@cli.command()
def version() -> None:
    """Print the version and exit."""
    click.echo(__version__)


# --------------------------------------------------------------------------- #
# Sub-command: man                                                            #
# --------------------------------------------------------------------------- #
@cli.command()
@click.pass_context
def man(ctx: click.Context) -> None:
    """Print the man page and exit."""
    click.echo(_emit_manpage("showcov", cli))
    ctx.exit(EXIT_OK)


# --------------------------------------------------------------------------- #
# Sub-command: completion                                                     #
# --------------------------------------------------------------------------- #
@cli.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False))
def completion(shell: str) -> None:
    """Print shell-completion script and exit."""
    script = click_completion.core.get_code(shell=shell, prog_name="showcov")
    click.echo(script)


# --------------------------------------------------------------------------- #
# Sub-command: show (default)                                                 #
# --------------------------------------------------------------------------- #
@cli.command(name="show")
@click.argument("paths", nargs=-1, type=click.Path())
# input
@click.option(
    "--cov", "xml_file", type=click.Path(path_type=Path, exists=True), help="Path to coverage XML file"
)
@click.option("--exclude", multiple=True, help="Glob pattern to exclude (can be repeated)")
@click.option("--include", "include_", multiple=True, help="Glob pattern to include (can be repeated)")
# output routing / styling
@click.option(
    "--format",
    "format_",
    default="auto",
    show_default=True,
    type=click.Choice(["auto", "human", "json", "markdown", "sarif"], case_sensitive=False),
    help="Output format",
)
@click.option("--pager", is_flag=True, help="Force paging even if stdout is redirected")
@click.option("--no-pager", is_flag=True, help="Disable paging even if stdout is a TTY")
@click.option("--color", "force_color", is_flag=True, help="Force ANSI color codes in output")
@click.option("--no-color", is_flag=True, help="Disable ANSI color codes in output")
@click.option("--output", type=click.Path(path_type=Path), help="Write output to FILE instead of stdout")
# output content flags
@click.option("--paths/--no-paths", "show_paths", default=True, help="Include file paths in output")
@click.option("--file-stats/--no-file-stats", default=False, help="Include per-file statistics")
@click.option("--stats/--no-stats", "aggregate_stats", default=False, help="Include aggregate statistics")
@click.option("--code/--no-code", "show_code", default=False, help="Include the uncovered source code lines")
# code-specific
@click.option("--line-numbers", is_flag=True, help="Show line numbers alongside code")
@click.option(
    "--context",
    "context_",
    type=str,
    metavar="N[,M]",
    help="Lines of context to include: N for both sides or N,M for before/after",
)
@click.pass_obj
def show(
    opts: ShowcovOptions,
    *,
    paths: Sequence[str],
    xml_file: Path | None,
    include_: Sequence[str],
    exclude: Sequence[str],
    format_: str,
    pager: bool,
    no_pager: bool,
    force_color: bool,
    no_color: bool,
    output: Path | None,
    show_paths: bool,
    file_stats: bool,
    aggregate_stats: bool,
    show_code: bool,
    line_numbers: bool,
    context_: str | None,
) -> None:
    """Show uncovered lines (default command)."""
    kwargs = locals()  # magic way to capture all kwargs at once
    opts = parse_flags_to_opts(**kwargs)

    _configure_runtime(
        quiet=opts.quiet,
        verbose=opts.verbose,
        debug=opts.debug,
    )

    try:
        sections, resolved_xml = resolve_sections(opts)
    except CoverageXMLNotFoundError as e:
        click.echo(f"ERROR: {e}", err=True)
        if opts.debug:
            raise
        sys.exit(EXIT_NOINPUT)
    except ElementTree.ParseError:
        click.echo(f"ERROR: failed to read coverage XML (invalid format): {xml_file or '<auto>'}", err=True)
        if opts.debug:
            raise
        sys.exit(EXIT_DATAERR)
    except OSError as e:
        click.echo(f"ERROR: failed to read coverage XML: {e}", err=True)
        if opts.debug:
            raise
        sys.exit(EXIT_GENERIC)

    is_tty = sys.stdout.isatty()
    actual_format = determine_format(opts, output, is_tty=is_tty)
    output_text = render_output(sections, opts, actual_format, resolved_xml)
    write_output(output_text, opts)
