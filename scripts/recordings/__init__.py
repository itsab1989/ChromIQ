# SPDX-License-Identifier: GPL-3.0-or-later
"""Read USB recordings of an instrument's own program, for a driven-instrument integration.

Standard library only. Nothing here opens a device or sends anything: it reads a recording file
and prints what is in it. The device-specific part (how a line looks, which lines the app may
send) lives in a small plug-in under ``scripts/recordings/plugins/``.

* ``capture``: pcap / pcapng reader and USB event extraction (macOS, Windows USBPcap, Linux
  usbmon), plus a writer for SYNTHETIC recordings used by the tests and the examples.
* ``plugins``: the plug-in interface and the registry; ``plugins/i1io2_table.py`` is the i1iO 2
  table's plug-in, built only from what ``workflow/i1io/table/`` already says in public.
* ``synthetic``: makes a small invented i1iO 2 recording to try the tools on.

The two programs that use it are ``scripts/recording_timeline.py`` and
``scripts/recording_vs_allowlist.py``; ``docs/adding_an_instrument.md`` section 12b explains the
method, and ``scripts/README.md`` the rules every script here follows.
"""
