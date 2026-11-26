"""Tests for the agent configuration.

The settings come from the ``[agent]`` section of the configuration, and the
API key comes from the environment variable that the section names. The key is
never read from the configuration and never appears in an error message.
"""

from __future__ import annotations

import pytest

from aturb.agent.config import agent_settings, read_api_key
from aturb.agent.types import AgentError
from aturb.config import ConfigError

DEFAULTS = {
    "provider": "openai_compatible",
    "model": "",
    "base_url": "",
    "api_key_env": "ATURB_AGENT_API_KEY",
    "max_input_tokens": 20000,
    "max_output_tokens": 8000,
    "max_cost_usd": 0.50,
    "max_attempts": 3,
    "max_total_cost_usd": 0.75,
    "max_total_input_tokens": 60_000,
    "max_total_output_tokens": 24_000,
    "input_price_per_mtok": 0.0,
    "output_price_per_mtok": 0.0,
    "timeout_s": 120,
    "reasoning_effort": "",
}

OVERRIDES = {
    "provider": "another_provider",
    "model": "some-model-id",
    "base_url": "https://example.invalid/v1",
    "api_key_env": "MY_MODEL_KEY",
    "max_input_tokens": 1234,
    "max_output_tokens": 567,
    "max_cost_usd": 1.25,
    "max_attempts": 5,
    "max_total_cost_usd": 2.5,
    "max_total_input_tokens": 12345,
    "max_total_output_tokens": 6789,
    "input_price_per_mtok": 0.15,
    "output_price_per_mtok": 0.60,
    "timeout_s": 45,
    "reasoning_effort": "high",
}

KEY = "secret-key-must-not-be-logged"


def test_the_defaults_are_filled_in():
    """A configuration without an agent section gives the defaults."""
    settings = agent_settings({})

    assert settings == DEFAULTS


def test_a_missing_agent_section_gives_the_defaults():
    """A configuration with other sections gives the defaults."""
    settings = agent_settings(
        {"active_pack": "stub", "timeouts": {"build_s": 60}})

    assert settings == DEFAULTS


def test_the_settings_hold_exactly_the_supported_keys():
    """The settings hold the supported keys and nothing else."""
    settings = agent_settings({"agent": {"unknown_key": "ignored"}})

    assert set(settings) == set(DEFAULTS)
    assert "unknown_key" not in settings


@pytest.mark.parametrize("key", sorted(OVERRIDES))
def test_every_setting_can_be_overridden(key):
    """Every supported setting is taken from the configuration."""
    value = OVERRIDES[key]
    settings = agent_settings({"agent": {key: value}})

    assert settings[key] == value
    for other in DEFAULTS:
        if other != key:
            assert settings[other] == DEFAULTS[other]


def test_an_agent_section_that_is_not_a_table_raises():
    """A section that is not a table is refused."""
    with pytest.raises(AgentError):
        agent_settings({"agent": "not a table"})


def test_the_key_is_read_from_the_environment():
    """The key is read from the variable that the settings name."""
    settings = agent_settings({"agent": {"api_key_env": "MY_MODEL_KEY"}})

    key = read_api_key(settings, {"MY_MODEL_KEY": KEY})

    assert key == KEY


def test_a_missing_environment_variable_raises():
    """A variable that is not set is refused."""
    settings = agent_settings({"agent": {"api_key_env": "MY_MODEL_KEY"}})

    with pytest.raises(AgentError) as excinfo:
        read_api_key(settings, {})

    assert "MY_MODEL_KEY" in str(excinfo.value)


def test_an_empty_environment_variable_raises():
    """A variable that is empty is refused."""
    settings = agent_settings({"agent": {"api_key_env": "MY_MODEL_KEY"}})

    with pytest.raises(AgentError):
        read_api_key(settings, {"MY_MODEL_KEY": ""})


def test_settings_without_a_named_variable_raise():
    """Settings that name no variable are refused."""
    settings = agent_settings({"agent": {"api_key_env": ""}})

    with pytest.raises(AgentError):
        read_api_key(settings, {"MY_MODEL_KEY": KEY})


def test_the_key_is_never_read_from_the_configuration():
    """A key in the configuration is ignored."""
    settings = agent_settings({"agent": {"api_key": KEY}})

    assert "api_key" not in settings
    with pytest.raises(AgentError):
        read_api_key(settings, {})


@pytest.mark.parametrize(
    "env",
    [{}, {"MY_MODEL_KEY": ""}, {"OTHER_KEY": KEY}],
)
def test_the_key_is_in_no_error_message(env):
    """No error message carries the API key."""
    settings = agent_settings({"agent": {"api_key_env": "MY_MODEL_KEY"}})

    with pytest.raises(AgentError) as excinfo:
        read_api_key(settings, env)

    assert KEY not in str(excinfo.value)


@pytest.mark.parametrize("key", [
    "max_attempts", "max_total_cost_usd", "max_total_input_tokens",
    "max_total_output_tokens",
])
def test_loop_limits_must_be_numbers(key):
    """A boolean or text is not a numeric loop bound."""
    for value in (True, "3"):
        with pytest.raises(AgentError):
            agent_settings({"agent": {key: value}})


def test_loop_limits_have_a_positive_attempt_bound_and_nonnegative_caps():
    """The attempt bound is at least one and cumulative caps are non-negative."""
    for key, value in (("max_attempts", 0), ("max_total_cost_usd", -0.1),
                       ("max_total_input_tokens", -1),
                       ("max_total_output_tokens", -1)):
        with pytest.raises(AgentError):
            agent_settings({"agent": {key: value}})


def test_the_reasoning_effort_is_optional():
    """A configuration that names no reasoning effort leaves it unset."""
    settings = agent_settings({})

    assert settings["reasoning_effort"] == ""


def test_the_reasoning_effort_is_taken_from_the_configuration():
    """A named reasoning effort is kept as it is."""
    settings = agent_settings({"agent": {"reasoning_effort": "low"}})

    assert settings["reasoning_effort"] == "low"


def test_the_reasoning_effort_is_stored_stripped():
    """A reasoning effort with spaces around it is stored without them."""
    settings = agent_settings({"agent": {"reasoning_effort": "  high  "}})

    assert settings["reasoning_effort"] == "high"


@pytest.mark.parametrize("value", [1, True, 1.5, ["low"], {"effort": "low"}])
def test_a_reasoning_effort_that_is_not_text_raises(value):
    """A reasoning effort that is not text is refused."""
    with pytest.raises(ConfigError):
        agent_settings({"agent": {"reasoning_effort": value}})


@pytest.mark.parametrize("value", [" ", "low high", "low\thigh", "\n"])
def test_a_reasoning_effort_that_holds_whitespace_raises(value):
    """A reasoning effort that holds whitespace is refused."""
    with pytest.raises(ConfigError):
        agent_settings({"agent": {"reasoning_effort": value}})


def test_a_bad_reasoning_effort_is_also_an_agent_error():
    """A refused reasoning effort is an agent error, as every other setting is."""
    with pytest.raises(AgentError):
        agent_settings({"agent": {"reasoning_effort": 3}})
