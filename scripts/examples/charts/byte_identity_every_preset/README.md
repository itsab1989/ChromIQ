# Example: every built-in preset, byte for byte, in two trees

Kept as a worked pattern from the page-output Beta (4.3.43) and its units round (4.3.44); it may
need adapting to the option you are proving. The method is in
`docs/adding_an_instrument.md`, section 9b.

1. Check the previous release out into its own worktree, next to your branch.
2. In each tree, with sandboxed settings, presets and logs (all three variables, each a new
   location), run `identity_driver.py <tree> <new file>.json --mode off` with the same
   `--pin-version`. It opens the real app on screen, loads every built-in preset in turn,
   presses Generate, and hashes every file each build writes.
3. `compare_identity.py a.json b.json` prints the table; exit 1 when anything differs.
4. Run it twice: the release against your branch with the option off, and your branch off
   against your branch on with nothing new used. Both must show no difference.
5. Where you kept the built files (`PB_KEEP`), `masked_compare.py` compares them with the clock
   and the folder names masked, for a look at what really differs.

Change the block marked "THE OPTION UNDER TEST" in `identity_driver.py` for your own option.
Nothing here deletes anything; the built files stay in your `CHROMIQ_LOG_DIR`.
