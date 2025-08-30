from __future__ import annotations

import argparse
from pathlib import Path
import sys
import logging
from simpleagent.cli import get_prog_name, CLI
from simpleagent import ConfigManager, ConfigError
from simpleagent.model import LLM
import asyncio

def configure_logging(log_level: str):
    """Configure logging for the application.
    
    Args:
        log_level: The log level to use (debug, info, warning, error, critical).
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stderr,
    )
    
    # Set log levels for specific loggers
    loggers = [
        'simpleagent',
        'langchain',
        'langchain_mcp_adapters'
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
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    prog = get_prog_name()
    args = parse_args(argv)
    log = logging.getLogger("main")
    try:
        log.info("Loading configuration from %s", args.config)
        cfgmgr = ConfigManager(args.config)
        cfg =cfgmgr.load_config()
    except ConfigError as e:
        logging.error("Failed to load configuration: %s", e)
        return 2

    # Print a concise summary to confirm successful load
    log.info("Configuration loaded successfully. Summary:")
    log.info("Loading model")
    llm = LLM(cfg.model.provider, cfg.model.name, cfg.model.max_tokens)
    log.info("model loaded")
    
    cli = CLI(prog, llm, cfg, args.root)
    await cli.run()
    return 0


if __name__ == "__main__":
    asyncio.run(main())
