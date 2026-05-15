import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    http_settings: dict[str, Any] = field(
        default_factory=lambda: {"host": "127.0.0.1", "port": 3000}
    )
    ws_settings: dict[str, Any] = field(
        default_factory=lambda: {"host": "127.0.0.1", "port": 3001, "role": "client"}
    )
    llm_auth: dict[str, Any] = field(default_factory=dict)
    # Legacy fallback for older config.yaml files. New configs should use
    # agent_config.openhands.model.
    llm_models: dict[str, Any] = field(default_factory=dict)
    agent_config: dict[str, Any] = field(
        default_factory=lambda: {
            "runtime": "openhands",
            "gateway": {
                "enabled": True,
                "allowed_sessions": [],
                "allowed_private_users": [],
                "allowed_groups": [],
                "allow_private_without_list": False,
            },
            "openhands": {
                "model": "gpt-5.4",
                "workspace": ".",
                "system_prompt": "",
                "condenser": {
                    "enabled": True,
                    "max_size": 80,
                    "max_tokens": 120000,
                    "keep_first": 2,
                    "minimum_progress": 0.1,
                },
                "mcp_servers": {
                    "qqio": {
                        "transport": "stdio",
                        "command": "",
                        "args": ["-m", "src.mcp.qqio"],
                        "cwd": ".",
                        "env": {},
                    },
                },
            },
        }
    )
    log_level: str = "INFO"

    @classmethod
    def from_yaml(cls) -> "Config":
        project_root = Path(__file__).resolve().parents[2]
        yaml_file = project_root / "config.yaml"
        template_path = project_root / "template" / "config_template.yaml"

        if not yaml_file.exists():
            shutil.copy(template_path, yaml_file)
            raise FileNotFoundError(
                "配置文件不存在，已从template文件夹复制默认配置文件，请完善llm_auth等配置。"
            )

        with yaml_file.open("r", encoding="utf-8") as file:
            config_data = yaml.safe_load(file) or {}

        config = cls()
        for field_name, field_value in config_data.items():
            if not hasattr(config, field_name):
                continue
            current_value = getattr(config, field_name)
            if isinstance(current_value, dict) and isinstance(field_value, dict):
                setattr(config, field_name, _deep_merge(current_value, field_value))
            elif isinstance(current_value, list):
                setattr(config, field_name, field_value if isinstance(field_value, list) else [])
            else:
                setattr(config, field_name, field_value)

        if not config.llm_auth:
            raise ValueError("配置文件中缺少必需字段: llm_auth")
        return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


global_config = Config.from_yaml()

if os.getenv("ENV") == "DOCKER":
    global_config.ws_settings["host"] = "0.0.0.0"
    global_config.ws_settings["role"] = "server"
    global_config.http_settings["host"] = "napcat"
    openhands_config = global_config.agent_config.setdefault("openhands", {})
    mcp_servers = openhands_config.setdefault("mcp_servers", {})
    qqio_server = mcp_servers.setdefault("qqio", {})
    qqio_env = qqio_server.setdefault("env", {})
    qqio_env.setdefault("TANPOPO_HTTP_HOST", "napcat")
    qqio_env.setdefault("TANPOPO_HTTP_PORT", "3000")
    print("Using docker config")
