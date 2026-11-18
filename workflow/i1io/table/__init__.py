"""ChromIQ driving an X-Rite i1iO 2 table itself (part of the i1iO Beta).

The modules here came from the table owner's tester program chromiq-i1io-session 0.6.0
(``tools/i1io_session/`` on branch ``tester/i1io-session-0.6.0``), moved as files so that its
safety reviews and tests stay valid. The only edits: package-relative imports, and the reader
finds ChromIQ's own helper (``native/chromiq-chartread``) instead of the tester's ``bin/``.

Since 4.3.45 the Measure tab's table panel (``ui/i1io_table_window.py``) drives it, with the Beta
"X-Rite i1iO support" on, through ``TableJob`` (``job.py``). No file of the app imports this
package at module level; only that window (and the Beta's preparation code) import it inside a
function, after START on an i1iO 2 chart: ``tests/test_i1io_table_not_reached_by_the_app.py``
pins that, so with the Beta off nothing of it is loaded. The behaviour is specified, awaiting
confirmation, in ``docs/design/i1io_table_support.md``.
"""
