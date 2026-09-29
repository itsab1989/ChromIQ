# Four pre-existing defects, reproduced ON SCREEN on HEAD (4d0670b4)

Found while reviewing the CR30/density work; none of them is a regression from
it, all four reproduce on master. Verified in a real window, because #1 does not
appear offscreen at all, which is why the whole test suite is blind to it.
Probe: scratchpad/probe_preexisting.py (real MainWindow, sandboxed settings,
instrument picked through the real combo popup with the keyboard).

## D-A  `_apply_ui_state` does not restore the Guided instrument on screen
    stored guided row : instrument = CR30
    panel afterwards  : ColorMunki
This is, word for word, the symptom Basti reported this morning about the
Youtube project ("in guided mode it shows colormunki"). It only shows in a real
window; every offscreen probe of the same sequence came back clean. Suspected
cause (from the earlier review, NOT yet confirmed by me): the
`_link_instrument_controls` Guided/Manual mirror races the restore.

## D-B  a Guided CR30 hexagon chart hands `-h` to Manual as empty
    Guided : instrument CR30, hexagons ON
    Manual : -i = 'CR30', -h = ''
So building the same chart from Manual gives a rectangular sheet. The
instrument crosses over; the option that goes with it does not.

## D-C  `left_border` survives hidden, and is stored
    i1Pro : left_border ticked
    CR30  : the box is hidden, still ticked, and `_shared_get` returns True
Its three siblings (`_dd_check`, `_td_check`, `_nsl_check`) are all cleared when
hidden; this one is not. It cannot reach `printtarg -L` (gated by instrument),
but it IS passed to the layout engine ungated as `suppress_left_clip`
(ui/tabs/tab_chart.py:178) and it IS written into the run's stored UI state.

## D-D  `engine_recipe` disagrees with the Guided row (HALF of it)
    guided        : instrument CR30, double_density True
    engine_recipe : instrument CR30, hflag False
The instrument now agrees (it did not this morning). `hflag` still does not:
the engine recipe comes from `_manual_layout_panel.get_recipe()` unconditionally
(tab_chart.py:14953), and only `_transfer_guided_to_manual` ->
`_apply_guided_engine_recipe` ever writes a Guided choice into that panel, which
a Guided build never calls. So a run records a hexagonal chart in one field and
a rectangular one in another.
