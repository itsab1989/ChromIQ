"""ChromIQ driving an X-Rite i1iO 2 table itself (part of the i1iO Beta; NOT WIRED IN YET).

The modules here came from the table owner's tester program chromiq-i1io-session 0.6.0
(``tools/i1io_session/`` on branch ``tester/i1io-session-0.6.0``), moved as files so that its
safety reviews and tests stay valid. The only edits: package-relative imports, and the reader
finds ChromIQ's own helper (``native/chromiq-chartread``) instead of the tester's ``bin/``.

Nothing in the app imports this package yet (no menu, no window, no setting):
``tests/test_i1io_table_not_reached_by_the_app.py`` pins that. Wiring it in is a later step that
needs the owner's approval of the specification amendment (``docs/design/i1io_table_support.md``).
"""
