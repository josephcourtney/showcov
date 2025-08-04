import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from jsonschema import validate

from showcov.mcp_server import RESOURCE_URI, create_server


def test_mcp_resource_round_trip(coverage_xml_file: Callable[..., Path]) -> None:
    src = Path("tests/data/sample.py")
    xml = coverage_xml_file({src: [2, 4, 5]})
    server = create_server(coverage_xml=xml, context_lines=1, with_code=True)
    server_any = cast("Any", server)

    resources = asyncio.run(server_any.list_handler())
    assert len(resources) == 1
    res = resources[0]
    assert str(res.uri) == RESOURCE_URI
    assert res.mimeType == "application/json"
    assert res.readOnly is True
    assert res.meta == {"source": {"coverage_xml": str(xml.resolve())}}

    contents = asyncio.run(server_any.read_handler(RESOURCE_URI))
    assert len(contents) == 1
    payload = contents[0].content
    data = json.loads(payload)
    schema = json.loads(Path("src/showcov/data/mcp_schema.json").read_text(encoding="utf-8"))
    validate(data, schema)

    expected = json.loads(Path("tests/snapshots/mcp_server_payload.json").read_text(encoding="utf-8"))
    data["version"] = expected["version"] = "IGNORED"
    data["environment"]["coverage_xml"] = expected["environment"]["coverage_xml"] = "IGNORED"
    assert data == expected
