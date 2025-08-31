from __future__ import annotations

import argparse
from pathlib import Path
import sys
import signal
import logging
import os
import subprocess
from asyncio import subprocess as aio_subprocess
from simpleagent.repl import get_prog_name, REPL
from simpleagent import ConfigManager, ConfigError
from simpleagent.model import LLM
from simpleagent.ui import SimpleAgentUI
import threading
from simpleagent.ui.pathcompleter import AtPathSuggester, DictAutocompleteProvider, CompositeAutocompleteProvider

import asyncio
import nest_asyncio
nest_asyncio.apply()

log = logging.getLogger("main")


def configure_logging(log_level: str, prog_name: str):
    """Configure logging to a file instead of the UI.

    Args:
        log_level: The log level to use (debug, info, warning, error, critical).
        ui_instance: Unused; kept for backward compatibility with existing calls.
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # File handler writes logs to the project directory (absolute path)
    log_file = str(Path.cwd() / f'{prog_name}.log')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    # Clear any existing handlers
    root_logger.handlers.clear()
    # Add file handler
    root_logger.addHandler(file_handler)
    
    # Set log levels and propagation for specific loggers (including MCP libs)
    loggers = [
        'simpleagent',
        'simpleagent.model',
        'simpleagent.graph',
        'langchain_mcp_adapters',
        'mcp',
        'mcp.server',
        'mcp.client',
    ]

    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(numeric_level)
        # Remove any pre-existing handlers that could print to console
        logger.handlers.clear()
        # Ensure they propagate to root so our file handler captures them
        logger.propagate = True
    
    logging.info(f"Logging configured with level: {log_level.upper()} -> {log_file}")



def parse_args(prog, argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="simpleagent runner")
    default_cfg_path = Path.home() / f".{prog}" / "config.json"

    parser.add_argument(
        "--config",
        help=f"Path to configuration JSON file (default {default_cfg_path})",
        default=default_cfg_path
    )
    parser.add_argument(
        "--root",
        dest="root",
        type=str,
        help="Root directory used for '@' file path autocompletion.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug level logging",
    )
    return parser.parse_args(argv)



async def main(argv: list[str] | None = None) -> int:


    prog = get_prog_name()
    # Wait for UI ready (so handler won’t hit uninitialized attributes)
    
    args = parse_args(prog, argv)

    # Configure logging after UI is ready
    configure_logging("debug" if args.debug else "info", prog)
    try:
        if not args.config:
            args.config = Path.home() / f".{prog}" / "config.json"
        log.info("Loading configuration from %s", args.config)
        cfgmgr = ConfigManager(args.config)
        cfg = cfgmgr.load_config()
    except ConfigError as e:
        logging.error("Failed to load configuration: %s", e)
        return 2

    # Print a concise summary to confirm successful load
    log.info("Configuration loaded successfully. Summary:")
    log.info("Loading model")
    llm = LLM(cfg.model.provider, cfg.model.name, cfg.model.max_tokens)
    log.info("model loaded")


    pathProvider=AtPathSuggester(args.root)
    cmdProvider=DictAutocompleteProvider("/", {"help", "quit", "exit"})
    autoCompleteProvider=CompositeAutocompleteProvider([pathProvider, cmdProvider])
    ui = SimpleAgentUI(prog,autoCompleteProvider)
    # Start UI asynchronously and wait for mount before logging


    cli = REPL(prog, llm, cfg, args.root, ui)
    await cli.init()
    await cli.run()

    ui.run()
    if getattr(ui, "ready_event", None) is not None:
        await ui.ready_event.wait()

    return 0

async def shutdown(loop):
    print("Shutting down...")
    tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

def custom_exception_handler(loop, context):
    exception = context.get("exception")
    if isinstance(exception, SystemExit) and exception.code == 0:
        log.debug("Ignoring SystemExit(0) for background task.")
        pass
    else:
        loop.default_exception_handler(context)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(custom_exception_handler)
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown(loop)))
    try:
        loop.run_until_complete(main())
    except SystemExit:
        pass
    except asyncio.CancelledError:
        pass # Expected during shutdown
    finally:
        loop.close()
