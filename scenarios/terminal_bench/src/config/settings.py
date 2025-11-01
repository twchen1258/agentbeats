"""Config loader for terminal-bench green agent."""

import os
import tomllib
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv()


class ConfigurationError(Exception):
    """Configuration error."""
    pass


class Settings:
    """Load config from config.toml and environment variables."""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.toml"

        if not config_path.exists():
            raise ConfigurationError(f"Config file not found: {config_path}")

        try:
            with open(config_path, "rb") as f:
                self._config = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(f"Invalid TOML syntax: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value (env vars override TOML)."""
        # Check environment variable first
        env_val = os.getenv(key.upper().replace(".", "_"))
        if env_val is not None:
            return env_val

        # Get from TOML config
        value = self._config
        for k in key.split("."):
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value if value is not None else default

    def _required(self, key: str) -> Any:
        """Get required config value or raise error."""
        value = self.get(key)
        if value is None or (isinstance(value, str) and not value):
            raise ConfigurationError(f"Missing required config: {key}")
        return value

    @property
    def openai_api_key(self) -> str | None:
        return os.getenv("OPENAI_API_KEY")

    @property
    def green_agent_host(self) -> str:
        return self._required("green_agent.host")

    @property
    def green_agent_port(self) -> int:
        return int(self._required("green_agent.port"))

    @property
    def green_agent_card_path(self) -> str:
        return self._required("green_agent.card_path")

    @property
    def mcp_base_port(self) -> int:
        return int(self._required("mcp.base_port"))

    @property
    def white_agent_host(self) -> str:
        return self._required("white_agent.host")

    @property
    def white_agent_port(self) -> int:
        return int(self._required("white_agent.port"))

    @property
    def white_agent_model(self) -> str:
        return self._required("white_agent.model")

    @property
    def white_agent_url(self) -> str:
        return f"http://{self.white_agent_host}:{self.white_agent_port}"

    @property
    def agent_max_iterations(self) -> int:
        return int(self._required("white_agent.max_iterations"))

    @property
    def eval_output_path(self) -> str:
        return self._required("evaluation.output_path")

    @property
    def eval_n_attempts(self) -> int:
        return int(self._required("evaluation.n_attempts"))

    @property
    def eval_n_concurrent_trials(self) -> int:
        return int(self._required("evaluation.n_concurrent_trials"))

    @property
    def eval_timeout_multiplier(self) -> float:
        return float(self._required("evaluation.timeout_multiplier"))

    @property
    def eval_cleanup(self) -> bool:
        return bool(self._required("evaluation.cleanup"))

    @property
    def eval_task_ids(self) -> list[str]:
        task_ids = self._required("evaluation.task_ids")
        if isinstance(task_ids, str):
            return [t.strip() for t in task_ids.split(",")]
        return task_ids

    @property
    def dataset_name(self) -> str:
        return self._required("dataset.name")

    @property
    def dataset_version(self) -> str:
        return self._required("dataset.version")

    @property
    def log_level(self) -> str:
        return self._required("logging.level")

    @property
    def log_format(self) -> str:
        return self._required("logging.format")

    @property
    def a2a_message_timeout(self) -> float:
        return float(self._required("a2a.message_timeout"))

    @property
    def a2a_health_check_timeout(self) -> float:
        return float(self._required("a2a.health_check_timeout"))

    @property
    def difficulty_weights(self) -> dict[str, int]:
        """Get difficulty weights for scoring."""
        weights = self._required("scoring.difficulty_weights")
        return weights

    @property
    def task_difficulty_map(self) -> dict[str, str]:
        """Get task difficulty mapping for scoring."""
        task_map = self._required("scoring.task_difficulty_map")
        return task_map


settings = Settings()
