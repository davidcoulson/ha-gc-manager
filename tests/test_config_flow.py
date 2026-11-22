# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Tests for the GC Manager config and options flows."""

from unittest.mock import patch

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gc_manager.const import (
    CONF_DAILY_MAINTENANCE,
    CONF_DAILY_TIME,
    CONF_FREEZE_ON_START,
    CONF_PAUSE_GC_UNTIL_FREEZE,
    CONF_REFREEZE_INTERVAL_HOURS,
    CONF_REFREEZE_PAUSE_MS,
    CONF_SAMPLE_INTERVAL_MINUTES,
    CONF_SET_THRESHOLDS,
    CONF_STARTUP_DELAY_SECONDS,
    CONF_THRESHOLD_GEN0,
    CONF_THRESHOLD_GEN1,
    CONF_THRESHOLD_GEN2,
    DOMAIN,
    PAUSE_GC_WATCHDOG_SECONDS,
)

_INPUT = {
    CONF_FREEZE_ON_START: True,
    CONF_STARTUP_DELAY_SECONDS: 120,
    CONF_SAMPLE_INTERVAL_MINUTES: 5,
    CONF_REFREEZE_INTERVAL_HOURS: 6,
    CONF_PAUSE_GC_UNTIL_FREEZE: False,
    CONF_REFREEZE_PAUSE_MS: 250,
    CONF_DAILY_MAINTENANCE: True,
    CONF_DAILY_TIME: "04:00:00",
    CONF_SET_THRESHOLDS: False,
    CONF_THRESHOLD_GEN0: 2000,
    CONF_THRESHOLD_GEN1: 10,
    CONF_THRESHOLD_GEN2: 10,
}


async def test_user_flow_creates_single_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    with patch("custom_components.gc_manager.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == _INPUT


async def test_single_instance_only(hass):
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_updates(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=_INPUT)
    entry.add_to_hass(hass)
    with patch("custom_components.gc_manager.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM

        new = {**_INPUT, CONF_REFREEZE_INTERVAL_HOURS: 0, CONF_DAILY_MAINTENANCE: False}
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], new
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REFREEZE_INTERVAL_HOURS] == 0
    assert result["data"][CONF_DAILY_MAINTENANCE] is False


async def test_pause_without_freeze_on_start_is_rejected(hass):
    """pause_gc_until_freeze needs the startup freeze to run as its finisher.

    The combination is incoherent; the user step must re-show the form with
    an inline error instead of creating an entry that silently does nothing.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    bad = {**_INPUT, CONF_FREEZE_ON_START: False, CONF_PAUSE_GC_UNTIL_FREEZE: True}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_PAUSE_GC_UNTIL_FREEZE: "pause_requires_freeze_on_start"
    }


async def test_pause_with_startup_delay_above_watchdog_is_rejected(hass):
    """A startup_delay beyond the watchdog would have the failsafe preempt
    the freeze, defeating the pause silently."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    # Exact-boundary case: delay == watchdog is already lost because the freeze
    # only arms after the started event (S > 0), so T=S+watchdog > T=watchdog.
    bad = {
        **_INPUT,
        CONF_PAUSE_GC_UNTIL_FREEZE: True,
        CONF_STARTUP_DELAY_SECONDS: PAUSE_GC_WATCHDOG_SECONDS,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_STARTUP_DELAY_SECONDS: "startup_delay_exceeds_pause_watchdog"
    }


async def test_options_flow_rejects_pause_without_freeze_on_start(hass):
    """Same enforcement applies when reconfiguring via the options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=_INPUT)
    entry.add_to_hass(hass)
    with patch("custom_components.gc_manager.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        bad = {**_INPUT, CONF_FREEZE_ON_START: False, CONF_PAUSE_GC_UNTIL_FREEZE: True}
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], bad
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_PAUSE_GC_UNTIL_FREEZE: "pause_requires_freeze_on_start"
    }
