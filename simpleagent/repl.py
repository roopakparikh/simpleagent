
import os, sys, asyncio
import logging
from simpleagent.config import AppConfig
from pathlib import Path
from langchain_mcp_adapters.client import MultiServerMCPClient
from simpleagent.model import LLM
from simpleagent.graph import AgentGraph
from simpleagent.pathcompleter import get_path_completed_text
from simpleagent.ui import SimpleAgentUI
from simpleagent.ui.ui import ChatCallback

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



class REPL(ChatCallback):
    def __init__(self, prog: str, llm: LLM, cfg: AppConfig, root: Path, simpleagent_ui: SimpleAgentUI):
        self.prog = prog
        self.llm = llm
        self.cfg = cfg
        self.root = root
        self._get_resolved_root()
        self.simpleagent_ui = simpleagent_ui
        self.simpleagent_ui.set_chat_callback(self) 
        
    def _get_resolved_root(self):
        resolved_root = None
        try:
            candidate = os.path.abspath(os.path.expanduser(os.path.expandvars(self.root)))
            if os.path.isdir(candidate):
                resolved_root = candidate
            else:
                self._console_error(f"Provided --root is not a directory: {candidate}. Using current working directory.")
        except Exception as e:
            self._console_error(f"Failed to resolve --root '{root}': {e}. Using current working directory.")
        log.debug(f"Resolved --root to: {resolved_root}")
        self.resolved_root = resolved_root
    
    async def init(self):
        self.graph = AgentGraph(self.llm, self.cfg.mcpservers)
        await self.graph.init()

    def _console_info(self, msg: str):
        self.simpleagent_ui.console_out(msg)

    def _console_error(self, msg: str):
        self.simpleagent_ui.console_out(msg)

    async def run(self):
        self._console_info(f"{self.prog} Interactive CLI")
        self._console_info("Type your requests below. Use '@' followed by TAB to autocomplete file paths.")
        self._console_info("Type '/exit' or '/quit' to end the session.")
        self._console_info("Type '/help' for more commands.")
        self._console_info("")

    def on_input_submitted(self, message: str) -> None:
        line = message
        if self._handle_commands(line):
            return
        self._console_info("> "+line)
        self._console_info("Processing...")
        self.simpleagent_ui.input_out("")
        # Expand any @<path> occurrences to absolute paths before passing to tools
        line, path_mappings = get_path_completed_text(self.resolved_root, line)
        #self.simpleagent_ui.input_out(line)
        # Show that we're processing (for long-running tools)
        
        # Run the graph asynchronously
        res = asyncio.run(self.graph.run(line))
        
        # Display result
        if res:
            self._console_info(f"Result: {res}")
        else:
            self._console_info("No result returned.")
            
    
    def _handle_commands(self, line: str) -> bool:
        if line.strip().lower() in ("/exit", "/quit"):
            self._console_info("Goodbye!")
            sys.exit(0)
            return True
        if line.strip().lower() == "/help":
            self._console_info("Available commands:")
            self._console_info("  /exit, /quit: Exit the session")
            self._console_info("  /help: Show this help message")
            self._console_info("         to configure the LLM set the environment variable for LLM")
            self._console_info("         for Anthropic use ANTHROPIC_API_KEY")
            self._console_info("         for Ollama use OLLAMA_BASE_URL if you want non default usage")
            self._console_info("         --root must be supplied to initialize the working directory")
            self._console_info("         --config must be supplied to initialize the configuration")
            self._console_info(f"         default config is ~/.{self.prog}/config.json")
            return True
        return False
