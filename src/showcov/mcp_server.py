from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, cast

import click
from jsonschema import validate
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import Resource

from showcov.cli.util import ShowcovOptions, resolve_sections
from showcov.mcp import generate_llm_payload
from showcov.output.base import OutputMeta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic import AnyUrl

RESOURCE_URI = "showcov:coverage.json"


async def on_initialize(_: Context) -> None:
    """Handle server initialization."""


async def on_shutdown(_: Context) -> None:
    """Handle server shutdown."""


@asynccontextmanager
async def _lifespan(app: FastMCP) -> AsyncIterator[None]:  # pragma: no cover - exercised via handlers
    ctx = app.get_context()
    await on_initialize(ctx)
    try:
        yield
    finally:
        ctx = app.get_context()
        await on_shutdown(ctx)


def create_server(
    *,
    coverage_xml: Path,
    context_lines: int = 0,
    with_code: bool = False,
    debug: bool = False,
) -> FastMCP:
    """Return configured ``FastMCP`` server for showcov resources."""
    opts = ShowcovOptions(xml_file=coverage_xml)

    server = FastMCP("showcov", debug=debug, lifespan=_lifespan)

    @server._mcp_server.list_resources()  # noqa: SLF001
    async def list_resources() -> list[Resource]:  # pragma: no cover - exercised in tests
        await asyncio.sleep(0)
        return [
            Resource.model_validate({
                "name": "coverage",
                "uri": cast("AnyUrl", RESOURCE_URI),
                "description": "uncovered line report",
                "mimeType": "application/json",
                "readOnly": True,
                "_meta": {"source": {"coverage_xml": str(coverage_xml.resolve())}},
            })
        ]

    @server._mcp_server.read_resource()  # noqa: SLF001
    async def read_resource(
        uri: AnyUrl,
    ) -> list[ReadResourceContents]:  # pragma: no cover - exercised in tests
        await asyncio.sleep(0)
        if str(uri) != RESOURCE_URI:
            msg = f"unknown resource: {uri}"
            raise ValueError(msg)
        sections, resolved_xml = resolve_sections(opts)
        meta = OutputMeta(
            context_lines=context_lines,
            with_code=with_code,
            coverage_xml=resolved_xml,
            color=False,
        )
        payload = generate_llm_payload(sections, meta)
        data = json.loads(payload)
        schema = json.loads(
            resources.files("showcov.data").joinpath("mcp_schema.json").read_text(encoding="utf-8")
        )
        validate(data, schema)
        text = json.dumps(data, indent=2, sort_keys=True)
        return [ReadResourceContents(content=text, mime_type="application/json")]

    server.list_handler = list_resources  # type: ignore[attr-defined]
    server.read_handler = read_resource  # type: ignore[attr-defined]
    return server


@click.command()
@click.option("--debug", is_flag=True, help="enable debug output")
@click.option("--context", default=0, type=int, show_default=True, help="number of context lines")
@click.option("--with-code", is_flag=True, help="include raw source lines")
@click.option(
    "--cov",
    "coverage",
    type=click.Path(path_type=Path),
    default=Path("coverage.xml"),
    help="coverage XML path",
)
def main(*, debug: bool, context: int, with_code: bool, coverage: Path) -> None:
    """Run the showcov MCP server."""
    server = create_server(
        coverage_xml=coverage,
        context_lines=max(0, context),
        with_code=with_code,
        debug=debug,
    )
    server.run()


__all__ = ["RESOURCE_URI", "create_server", "main"]
