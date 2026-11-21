"""The settings of the agent.

The settings come from the ``[agent]`` section of the configuration file. The
API key is not one of them: the section names an environment variable and the
key is read from the environment, so the key never enters the configuration
file and never enters the repository.

The provider, the model and the endpoint are configuration, not code. Nothing
here knows a particular provider.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from aturb.agent.types import AgentError

DEFAULTS: dict[str, object] = {
    "provider": "openai_compatible",  # starting default
    "model": "",  # starting default
    "base_url": "",  # starting default
    "api_key_env": "ATURB_AGENT_API_KEY",  # starting default
    "max_input_tokens": 20000,  # starting default
    "max_output_tokens": 8000,  # starting default
    "max_cost_usd": 0.50,  # starting default
    "input_price_per_mtok": 0.0,  # starting default
    "output_price_per_mtok": 0.0,  # starting default
    "timeout_s": 120,  # starting default
}


def agent_settings(cfg: dict) -> dict:
    """Return the agent settings of a configuration, with the defaults filled in.

    Only the supported settings are returned. A key that the section does not
    name keeps its default, and a key that the section names is taken as it
    stands.
    """
    section = cfg.get("agent", {})
    if not isinstance(section, dict):
        raise AgentError(
            "the 'agent' section of the configuration is not a table")
    settings = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in section:
            settings[key] = section[key]
    return settings


def read_api_key(settings: dict, env: Mapping[str, str] | None = None) -> str:
    """Return the API key that the settings name, read from the environment.

    The key is never read from the configuration and never appears in an error
    message: the message names the environment variable, not its value.
    """
    name = settings.get("api_key_env", "")
    if not isinstance(name, str) or not name:
        raise AgentError(
            "the agent settings do not name an environment variable for the API key")
    source = os.environ if env is None else env
    key = source.get(name, "")
    if not key:
        raise AgentError(
            f"the environment variable {name} is not set or is empty")
    return key
