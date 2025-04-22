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

## License

This project is licensed under the [MIT License](LICENSE).
