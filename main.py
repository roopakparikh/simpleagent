from __future__ import annotations

import argparse
from pathlib import Path
import sys
import signal
import logging
from simpleagent.repl import get_prog_name, REPL
from simpleagent import ConfigManager, ConfigError
from simpleagent.model import LLM
import asyncio
import nest_asyncio
nest_asyncio.apply()

log = logging.getLogger("main")

def configure_logging(log_level: str):
    """Configure logging for the application.
    
    Args:
        log_level: The log level to use (debug, info, warning, error, critical).
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stderr,
    )
    
    # Set log levels for specific loggers
    loggers = [
        'simpleagent',
        'simpleagent.model',
        'simpleagent.graph'
        #'langchain',
        #'langchain_mcp_adapters'
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(numeric_level)
    
    logging.info(f"Logging configured with level: {log_level.upper()}")


def parse_args(prog, argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="simpleagent runner")
    default_cfg_path = Path.home() / f".{prog}" / "config.json"

    parser.add_argument(
        "--config",
        required=True,
        help=f"Path to configuration JSON file (default {default_cfg_path})",
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
    args = parse_args(prog, argv)
    # Configure logging early based on --debug
    configure_logging("debug" if args.debug else "info")
    try:
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
    
    cli = REPL(prog, llm, cfg, args.root)
    await cli.init()
    await cli.run()
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
