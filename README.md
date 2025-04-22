# showcov

showcov is a command-line utility that prints uncovered lines of code—grouped into contiguous sections—from a coverage XML report.

## Installation

```bash
uv tool install clone https://github.com/josephcourtney/showcov.git
```

## Usage

```bash
showcov [COVERAGE_XML_FILE]
```

- **COVERAGE_XML_FILE**: _(Optional)_ The path to your coverage XML report.  
  If omitted, showcov will search for a configuration file (such as `pyproject.toml`, `.coveragerc`, or `setup.cfg`) that specifies the XML report’s location.

Result for showcov itself:

```bash
INFO: Using coverage XML file from config: .coverage.xml

Uncovered sections in /Users/josephcourtney/code/showcov/src/showcov/__version__.py:
  Line 1:
       1: __version__ = "0.0.9"


Uncovered sections in /Users/josephcourtney/code/showcov/src/showcov/main.py:
  Line 25:
      25:     from xml.etree.ElementTree import Element  # noqa: S405

  Line 136:
     136:         return groups

  Line 199:
     199:             continue

  Lines 240-241:
     240:             logger.error("Failed to parse coverage XML file: %s", xml_file)
     241:             sys.exit(1)
```

## License

This project is licensed under the [MIT License](LICENSE).
