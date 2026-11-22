# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Config and options flow for GC Manager (single instance)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

try:
    # HA 2026.9 replaced voluptuous with the API-compatible probatio and types
    # schemas as probatio; build ours with whichever this HA ships.
    import probatio as vol
except ImportError:  # HA < 2026.9
    import voluptuous as vol  # type: ignore[no-redef]

from .const import (
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
    DEFAULT_DAILY_MAINTENANCE,
    DEFAULT_DAILY_TIME,
    DEFAULT_FREEZE_ON_START,
    DEFAULT_NAME,
    DEFAULT_PAUSE_GC_UNTIL_FREEZE,
    DEFAULT_REFREEZE_INTERVAL_HOURS,
    DEFAULT_REFREEZE_PAUSE_MS,
    DEFAULT_SAMPLE_INTERVAL_MINUTES,
    DEFAULT_SET_THRESHOLDS,
    DEFAULT_STARTUP_DELAY_SECONDS,
    DEFAULT_THRESHOLD_GEN0,
    DEFAULT_THRESHOLD_GEN1,
    DEFAULT_THRESHOLD_GEN2,
    DOMAIN,
    MAX_REFREEZE_INTERVAL_HOURS,
    MAX_REFREEZE_PAUSE_MS,
    MAX_SAMPLE_INTERVAL_MINUTES,
    MAX_STARTUP_DELAY_SECONDS,
    MIN_REFREEZE_INTERVAL_HOURS,
    MIN_SAMPLE_INTERVAL_MINUTES,
    MIN_STARTUP_DELAY_SECONDS,
    PAUSE_GC_WATCHDOG_SECONDS,
    UNIQUE_ID,
)

_THRESHOLD = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=1, max=100000, step=1, mode=selector.NumberSelectorMode.BOX
    )
)


def _build_schema(source: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_FREEZE_ON_START,
                default=source.get(CONF_FREEZE_ON_START, DEFAULT_FREEZE_ON_START),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_STARTUP_DELAY_SECONDS,
                default=source.get(
                    CONF_STARTUP_DELAY_SECONDS, DEFAULT_STARTUP_DELAY_SECONDS
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_STARTUP_DELAY_SECONDS,
                    max=MAX_STARTUP_DELAY_SECONDS,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_PAUSE_GC_UNTIL_FREEZE,
                default=source.get(
                    CONF_PAUSE_GC_UNTIL_FREEZE, DEFAULT_PAUSE_GC_UNTIL_FREEZE
                ),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SAMPLE_INTERVAL_MINUTES,
                default=source.get(
                    CONF_SAMPLE_INTERVAL_MINUTES, DEFAULT_SAMPLE_INTERVAL_MINUTES
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SAMPLE_INTERVAL_MINUTES,
                    max=MAX_SAMPLE_INTERVAL_MINUTES,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Required(
                CONF_REFREEZE_INTERVAL_HOURS,
                default=source.get(
                    CONF_REFREEZE_INTERVAL_HOURS, DEFAULT_REFREEZE_INTERVAL_HOURS
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_REFREEZE_INTERVAL_HOURS,
                    max=MAX_REFREEZE_INTERVAL_HOURS,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            ),
            vol.Required(
                CONF_REFREEZE_PAUSE_MS,
                default=source.get(CONF_REFREEZE_PAUSE_MS, DEFAULT_REFREEZE_PAUSE_MS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=MAX_REFREEZE_PAUSE_MS,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="ms",
                )
            ),
            vol.Required(
                CONF_DAILY_MAINTENANCE,
                default=source.get(CONF_DAILY_MAINTENANCE, DEFAULT_DAILY_MAINTENANCE),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_DAILY_TIME,
                default=source.get(CONF_DAILY_TIME, DEFAULT_DAILY_TIME),
            ): selector.TimeSelector(),
            vol.Required(
                CONF_SET_THRESHOLDS,
                default=source.get(CONF_SET_THRESHOLDS, DEFAULT_SET_THRESHOLDS),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_THRESHOLD_GEN0,
                default=source.get(CONF_THRESHOLD_GEN0, DEFAULT_THRESHOLD_GEN0),
            ): _THRESHOLD,
            vol.Required(
                CONF_THRESHOLD_GEN1,
                default=source.get(CONF_THRESHOLD_GEN1, DEFAULT_THRESHOLD_GEN1),
            ): _THRESHOLD,
            vol.Required(
                CONF_THRESHOLD_GEN2,
                default=source.get(CONF_THRESHOLD_GEN2, DEFAULT_THRESHOLD_GEN2),
            ): _THRESHOLD,
        }
    )


class GcManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return GcManagerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            errors = _validate_pause_combo(user_input)
            if not errors:
                await self.async_set_unique_id(UNIQUE_ID)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
            return self.async_show_form(
                step_id="user", data_schema=_build_schema(user_input), errors=errors
            )

        return self.async_show_form(step_id="user", data_schema=_build_schema({}))


class GcManagerOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            errors = _validate_pause_combo(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)
            return self.async_show_form(
                step_id="init", data_schema=_build_schema(user_input), errors=errors
            )

        source = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_build_schema(source))


def _validate_pause_combo(user_input: Mapping[str, Any]) -> dict[str, str]:
    """Enforce the two pause_gc_until_freeze invariants.

    Without a startup freeze there is no finisher for the pause; with a
    startup delay beyond the watchdog the failsafe preempts the freeze.
    """
    errors: dict[str, str] = {}
    if not user_input.get(CONF_PAUSE_GC_UNTIL_FREEZE):
        return errors
    if not user_input.get(CONF_FREEZE_ON_START):
        errors[CONF_PAUSE_GC_UNTIL_FREEZE] = "pause_requires_freeze_on_start"
    # `>=` not `>`: the watchdog is armed at setup (T=0, fires T=watchdog); the
    # freeze delay only arms after `async_at_started` (T=S, fires T=S+delay). On
    # any real cold boot S>0, so delay == watchdog loses the race too.
    if (
        int(user_input.get(CONF_STARTUP_DELAY_SECONDS, DEFAULT_STARTUP_DELAY_SECONDS))
        >= PAUSE_GC_WATCHDOG_SECONDS
    ):
        errors[CONF_STARTUP_DELAY_SECONDS] = "startup_delay_exceeds_pause_watchdog"
    return errors
