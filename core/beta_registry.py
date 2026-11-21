# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Every Beta switch and its sub-options, for the app log (4.3.50, A1).

The session header names each of these with its state, and
``AppSettings.set`` logs a change to any of them as it happens. A NEW SWITCH
ON PREFERENCES > BETA MUST BE ADDED HERE: ``tests/test_the_session_header_
names_every_beta_switch.py`` reads the Beta page's own save code and fails
for a key that is missing. No imports: ``core.settings`` imports this.
"""
from __future__ import annotations

#: the switches themselves (Preferences > Beta)
BETA_SWITCHES: "tuple[str, ...]" = (
    "profile_engine_beta",
    "engine_all_modes",
    "measure_calibrate_button",
    "scanner_hex_charts",
    "i1pro2_lights_beta",
    "ruler_check_beta",
    "margin_tolerance_beta",
    "i1pro3_conditions_beta",
    "i1pro2_dual_scan_beta",
    "i1profiler_turned_export",
    "fd9_support_beta",
    "i1io_support_beta",
    "isis_charts_beta",
    "page_output_beta",
    "splash_classic",
)

#: what the switches' own rows choose (lights, dual-scan instrument, the table's
#: guided measurement and calibration place, FD-9 rotation, ...)
BETA_SUB_OPTIONS: "tuple[str, ...]" = (
    "profile_engine_colprof_comparison",
    "i1pro2_lights_signals",
    "i1pro2_lights_during_reading",
    "i1pro2_lights_quiet_s",
    "i1pro2_blue_quiet_s",
    "i1pro2_blue_after_s",
    "i1pro_lamp_off_s",
    "dual_scan_instrument",
    "dual_scan_instrument_source",
    "i1pro2_dual_scan_mode",
    "i1io_table_ask_after_each_step",
    "i1io_table_extra_logging",
    "i1io_table_calibration_place",
    "i1io_table_stored_tile_white",
    "i1io_table_patch_by_patch",
    "i1io_table_row_speed_factor",
    "fd9_display_rotation",
)

#: ordinary options a reading depends on, named in the header beside the Betas
#: ("Warn me if a strip looks misaligned" is ``misalign_safenet``)
MEASURE_OPTIONS: "tuple[str, ...]" = (
    "chartread_engine",
    "misalign_safenet",
    "use_chromiq_layout_engine",
    "chromiq_refinement",
    "averaging_enabled",
    "calibration_mode",
)

#: the keys whose change ``AppSettings.set`` logs
LOGGED_KEYS = frozenset(BETA_SWITCHES + BETA_SUB_OPTIONS + MEASURE_OPTIONS)


def show(value) -> str:
    """One value as the log writes it: on/off for a bool, the text otherwise."""
    if isinstance(value, bool):
        return "on" if value else "off"
    if value is None or value == "":
        return "-"
    text = str(value)
    if text.lower() in ("true", "false"):
        return "on" if text.lower() == "true" else "off"
    return text.replace(" ", "_")
