
import os, sys, signal
import logging
from simpleagent.config import AppConfig
from pathlib import Path
from langchain_mcp_adapters.client import MultiServerMCPClient
from simpleagent.model import LLM
from simpleagent.graph import AgentGraph
from simpleagent.pathcompleter import get_prompt_session

log = logging.getLogger(__name__)

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


class REPL:
    def __init__(self, prog: str, llm: LLM, cfg: AppConfig, root: Path):
        self.prog = prog
        self.llm = llm
        self.cfg = cfg
        self.root = root
        self._get_resolved_root()

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
    
    async def init(self):
        self.graph = AgentGraph(self.llm, self.cfg.mcpservers)
        await self.graph.init()

    async def run(self):
        _console_info(f"{self.prog} Interactive CLI")
        _console_info("Type your requests below. Use '@' followed by TAB to autocomplete file paths.")
        _console_info("Type '/exit' or '/quit' to end the session.")
        _console_info("Type '/help' for more commands.")
        _console_info("")
        session = get_prompt_session(self.root)
        while True:
            try:
                line = session.prompt("> ")
                if self._handle_commands(line):
                    continue
                res = await self.graph.run(line)
                _console_info(res)
            except EOFError:
                _console_info("Goodbye!")
                break
            except Exception as e:
                log.exception(f"Error: {e}")
                _console_error(f"Error: {e}")
                break

    def _handle_commands(self, line: str) -> bool:
        if line.strip().lower() in ("/exit", "/quit"):
            _console_info("Goodbye!")
            sys.exit(0)
            return True
        if line.strip().lower() == "/help":
            _console_info("Available commands:")
            _console_info("  /exit, /quit: Exit the session")
            _console_info("  /help: Show this help message")
            _console_info("         to configure the LLM set the environment variable for LLM")
            _console_info("         for Anthropic use ANTHROPIC_API_KEY")
            _console_info("         for Ollama use OLLAMA_BASE_URL if you want non default usage")
            _console_info("         --root must be supplied to initialize the working directory")
            _console_info("         --config must be supplied to initialize the configuration")
            _console_info(f"         default config is ~/.{self.prog}/config.json")
            return True
        return False
