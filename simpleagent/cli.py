
import os, sys
import logging
from simpleagent.config import AppConfig
from pathlib import Path
from langchain_mcp_adapters.client import MultiServerMCPClient
from simpleagent.model import LLM

log = logging.getLogger("cli")

def get_prog_name() -> str:
    """Return the invoked program name (supports symlink renaming).

    Uses sys.argv[0] basename; if empty, falls back to 'simpleagent'.
    """
    try:
        base = os.path.basename(sys.argv[0]) or "simpleagent"
        return base
    except Exception:
        return "simpleagent"

def _console_info(msg: str):
    print(msg)

def _console_error(msg: str):
    print(msg)


class CLI:
    def __init__(self, prog: str, llm: LLM, cfg: AppConfig, root: Path):
        self.prog = prog
        self.llm = llm
        self.cfg = cfg
        self.root = root
        self._get_resolved_root()
        self.mcp_client = self._load_mcp_client()

    def _get_resolved_root(self):
        resolved_root = None
        try:
            candidate = os.path.abspath(os.path.expanduser(os.path.expandvars(self.root)))
            if os.path.isdir(candidate):
                resolved_root = candidate
            else:
                _console_error(f"Provided --root is not a directory: {candidate}. Using current working directory.")
        except Exception as e:
            _console_error(f"Failed to resolve --root '{root}': {e}. Using current working directory.")
        log.debug(f"Resolved --root to: {resolved_root}")
        self.resolved_root = resolved_root
    
    def _load_mcp_client(self):
        client = MultiServerMCPClient(connections=self.cfg.mcpservers)
        return client

    async def run(self):
        tools = await self.mcp_client.get_tools()
        _console_info(f"{self.prog} Interactive CLI")
        _console_info("Type your requests below. Use '@' followed by TAB to autocomplete file paths.")
        _console_info("Type '/exit' or '/quit' to end the session.")
        _console_info("Type '/help' for more commands.")
        _console_info("")