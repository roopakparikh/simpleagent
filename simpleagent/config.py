from __future__ import annotations


import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, field_validator



class ModelConfig(BaseModel):
    provider: str
    name: str
    max_tokens: int


class MCPServerConfig(TypedDict, total=False):
    """MCP server configuration.
    
    For stdio transport:
    - command: Required, the command to run
    - args: Optional, arguments to pass to the command
    
    For streamable_http/sse transport:
    - url: Required, the URL of the HTTP endpoint
    - headers: Optional, headers to include in requests
    """
    command: str
    url: str
    args: List[str]
    transport: str
    headers: Dict[str, str]



class AppConfig(BaseModel):
    model: ModelConfig
    mcpservers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('mcpservers')
    @classmethod
    def validate_server_config(cls, v):
        """Validate MCP server configurations based on transport type."""
        for server_name, server_config in v.items():
            transport = server_config.get('transport', 'stdio')
            
            # For stdio transport, command is required
            if transport == 'stdio':
                if 'command' not in server_config:
                    raise ValueError(f"Server '{server_name}' with stdio transport requires 'command' field")
            
            # For HTTP transports, url is required
            elif transport in ['streamable_http', 'sse']:
                if 'url' not in server_config:
                    raise ValueError(f"Server '{server_name}' with {transport} transport requires 'url' field")
        
        return v

class ConfigError(ValueError):
    """Raised when the configuration is invalid or cannot be loaded."""


class ConfigManager:
    """Load and validate simpleagent configuration files.
    """
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the config parser.
        
        Args:
            config_path: Path to the configuration file. If None, looks for
                        config.json in the current directory.
        """
        if config_path is None:
            config_path = "config.json"
        self.config_path = Path(config_path)
        self._config: Optional[AppConfig] = None
    
    def load_config(self) -> AppConfig:
        """Load configuration from file.
        
        Returns:
            Config: The loaded configuration object.
            
        Raises:
            FileNotFoundError: If the config file doesn't exist.
            json.JSONDecodeError: If the config file contains invalid JSON.
            ValueError: If the config file contains invalid data.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config_data = json.load(f)
        
        self._config = self.load_settings(config_data)
        return self._config


    def load_settings(self, config_data) -> AppConfig:
        """Load application settings from config.json file.
        
        Args:
            config_path: Optional path to the configuration file. If not provided,
                        will search for config.json in current and parent directories.
        
        Returns:
            Settings object with configuration loaded from config.json.
        """
        try:
            # Convert the JSON data to our Settings object
            return AppConfig(**config_data)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading configuration: {e}")