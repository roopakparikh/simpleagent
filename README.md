# simpleagent

[![Create Release](https://github.com/roopakparikh/simpleagent/actions/workflows/main.yaml/badge.svg)](https://github.com/roopakparikh/simpleagent/actions/workflows/main.yaml)

A lightweight CLI/TUI agent framework with path-aware autocomplete and optional MCP (Model Context Protocol) tool integration. Includes a Textual-based UI, logging to file, and packaging via PyInstaller.

## Features
- __Textual TUI__: header, output console, and a single input line.
- __Path Autocomplete__: type `@` and TAB to get file path suggestions from a configured root.
- __MCP tools__: discover and call tools via `langchain_mcp_adapters` (if configured).
- __Logging to file__: app logs go to `simpleagent.log` in the working directory.
- __PyInstaller packaging__: build a single binary locally or via GitHub Actions.

## Installation
Can be easily installed via the binary release. Download the latest release from the [releases page](https://github.com/rparikh/simpleagent/releases) and run it.

## DevRequirements
- Python 3.11+
- uv (recommended) or pip

## Dev Installation
Using uv (recommended):
```bash
uv sync --locked --all-extras --dev
```

## Configuration

The only tested LLM provider is Anthropic. The key has to be supplied as an env variable `ANTHROPIC_API_KEY`.
Ollama with llama3.1:8b was attempted but didn't perform well in tool calling, will need to try other models.

Provide a JSON config file. See `example-config.json` for a starting point.

Key fields typically include model provider/name and optional MCP server definitions. Example minimal schema:
```json
{
  "model": {
    "provider": "anthropic",
    "name": "claude-sonnet-4-20250514",
    "max_tokens": 64000
  },
  "mcpservers": {
    "weather" : {
      "command": "uv",
      "args": ["--directory", "/path/to/your/server/", "run", "sampleserver.py"],
      "transport": "stdio"
    },
    "gene-analysis" : {
      "command": "uv",
      "args": ["--directory", "/path/to/your/server/", "run", "longrun.py"],
      "transport": "stdio"
    }
 }
}
```

## Running
```bash
python ./main.py --config ./example-config.json --root .
```

Arguments:
- __--config__: path to JSON config. Default value is ~/.<prog name>/config.json
- __--root__: base directory for `@` path autocomplete.
- __--debug__: enable debug-level logging.

When the app starts you’ll see the TUI with a title and an input line. Type requests and press Enter.

## UI usage
- __Autocomplete__: type `@` followed by part of a path, press Up/Down to navigate, Enter to select.
- __Commands__:
  - `/help` shows commands
  - `/quit` or `/exit` to exit

Autocomplete behavior is implemented in:
- `simpleagent/ui/autocomplete.py` (`AutocompleteInput`, `AutocompletePopup`)
- `simpleagent/ui/pathcompleter.py` (`AtPathSuggester`)

## Logging
Logs are written to `simpleagent.log` in the current working directory. Tail them with:
```bash
tail -f simpleagent.log
```

You can adjust logging level at runtime by adding `--debug` to `main.py`, or edit `configure_logging()` in `main.py` to change destinations/format.

## MCP servers
If you define MCP servers in your config, they are loaded in `simpleagent/graph.py` via `MultiServerMCPClient`. Tool invocation occurs in `AgentGraph._node_tools()` and supports both async/sync tools and plain callables.

Note: Many MCP adapters communicate over stdio pipes and won’t emit raw process stdout/stderr to your terminal. App and adapter logs still go to `simpleagent.log`.

## Packaging (PyInstaller)
You can build a standalone binary with PyInstaller. A spec file is included (`simpleagent.spec`).

Local build example:
```bash
uv add pyinstaller   # or pip install pyinstaller
pyinstaller ./simpleagent.spec --clean
```
Artifacts will be placed under `dist/`.

## CI (GitHub Actions)
A workflow is provided at `.github/workflows/main.yaml` that:
- Installs uv and project deps
- Runs PyInstaller (ensure the spec path matches your repo; adjust if necessary)
- Creates a release for pushed tags (`v*`) and uploads the built asset

If you rename the spec or artifact, update the workflow keys:
- `Run PyInstaller`: spec filename
- `asset_name` / `asset_path`: distribution artifact

## Project structure
- `main.py`: entrypoint; config parsing, logging, UI/REPL wiring
- `simpleagent/ui/`: Textual UI, autocomplete, path completer
- `simpleagent/graph.py`: LangGraph-based agent with MCP tool loading
- `simpleagent/repl.py`: Bridges UI input to agent graph and prints results
- `example-config.json`: sample configuration

## Troubleshooting
- __No logs appear__: confirm `simpleagent.log` is created in the working directory; run with `--debug`.
- __Autocomplete not showing__: ensure you typed `@` before the path segment; check `AtPathSuggester.base_dir` matches `--root`.
- __MCP tools missing__: verify your config defines servers, and any external binaries are installed and on PATH.
- __PyInstaller errors__: confirm the spec file path and installed hooks; clear caches with `--clean`.

