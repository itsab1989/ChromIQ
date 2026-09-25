"""The button Return presses is FILLED in the window's accent (K44).

Knut, #182 5833776276 and 5833983335: nothing showed which button was a
window's default, while a few windows (Read Single Patches, the patch set
editor) filled their main button and the device-link window framed its own.
*"All windows and pop-up windows then should follow the same standard."*

The standard: **the button Return presses is drawn filled in the window's
accent** — the look ``QPushButton#primary`` has always had. The accent is the
window's own: its masthead's (``neutral_controls_qss(..., popup=accent)``), the
tab's for a window opened from a tab (the per-tab sheet in
``MainWindow``), otherwise the application's. In Neutral it is ACTION, as
every accent is.

Two things make "filled" and "Return" the same button, and keep them so:

* ``QPushButton:default`` is Qt's own ``isDefault()``, which is exactly the
  button a dialog's Return presses.
* :func:`freeze_default` (run for every window as it is shown) takes
  ``autoDefault`` off every OTHER button, so the default no longer follows the
  keyboard focus. Before that, tabbing to Cancel made Cancel the default for as
  long as it had focus, and a fill would have jumped with it. Space still
  presses the focused button; Return presses the filled one.

**A destructive question keeps a SAFE default** (Cancel, Keep, No) and that
button is NOT the main action, so it must not be drawn as one: mark it with
:func:`mark_safe_default` and it keeps the ordinary look.

This module knows no appearance and imports nothing from ``ui``; the three
application sheets call :func:`default_fill_qss` with their own tokens.
"""
from __future__ import annotations

#: The dynamic property that says "this default is the SAFE answer of a
#: destructive question, not the main action": it is drawn like any button.
SAFE_DEFAULT = "chromiq_safe_default"

#: The dynamic property on a button a window colours BY ITS OWN CODE (a
#: per-button style sheet), the way ``#primary`` is coloured by the sheets.
COLOURED = "chromiq_coloured"


def is_coloured(btn) -> bool:
    """Whether the window already colours *btn* itself: a ``#primary``, or a
    button marked with :func:`mark_coloured`."""
    return btn.objectName() == "primary" or bool(btn.property(COLOURED))


def mark_coloured(btn) -> None:
    """Say that *btn* is coloured by its own style sheet, so its window counts
    as one that already has a coloured button (Basti, 2026-09-25: such a
    window keeps its colours exactly as they are and gains no fill)."""
    btn.setProperty(COLOURED, True)


def default_fill_qss(*, accent: str, label: str, hover: str,
                     dis_bg: str, dis_border: str, dis_fg: str,
                     plain_bg: str, plain_border: str, plain_fg: str,
                     plain_hover_bg: str, plain_hover_border: str,
                     brace: bool = False) -> str:
    """The rules that fill a window's default button in ``accent``.

    ``plain_*`` is the ordinary button, restated for a safe default
    (:data:`SAFE_DEFAULT`): Qt prefers the nearest style sheet to the
    application's whatever the specificity, so a window that fills its default
    must also say, itself, what a safe default looks like.

    ``brace=True`` doubles every brace, for a caller that pastes the result
    into an f-string template (the application sheets are ``.format``-free
    f-strings built at import).
    """
    safe = f'QPushButton[{SAFE_DEFAULT}="true"]:default'
    s = (
        f"QPushButton:default {{ background: {accent};"
        f" border: 1px solid {accent}; color: {label}; font-weight: bold; }}\n"
        f"QPushButton:default:hover {{ background: {hover};"
        f" border-color: {hover}; }}\n"
        f"QPushButton:default:disabled {{ background: {dis_bg};"
        f" border: 1px solid {dis_border}; color: {dis_fg}; }}\n"
        f"{safe} {{ background: {plain_bg}; border: 1px solid {plain_border};"
        f" color: {plain_fg}; font-weight: normal; }}\n"
        f"{safe}:hover {{ background: {plain_hover_bg};"
        f" border-color: {plain_hover_border}; }}\n"
    )
    if brace:
        s = s.replace("{", "{{").replace("}", "}}")
    return s


def mark_safe_default(btn) -> None:
    """Keep *btn* the default (Return presses it) but draw it like any button:
    the safe answer of a destructive question is not the main action."""
    btn.setProperty(SAFE_DEFAULT, True)
    st = btn.style()
    if st is not None:
        st.unpolish(btn)
        st.polish(btn)
    btn.update()


def _role_is_safe(btn) -> bool:
    """Cancel / No / Close / Keep / Go back: a button-box REJECT or NO role."""
    from PyQt6.QtWidgets import QDialogButtonBox
    p = btn.parentWidget()
    while p is not None and not isinstance(p, QDialogButtonBox):
        if p.isWindow():
            return False
        p = p.parentWidget()
    if p is None:
        return False
    role = p.buttonRole(btn)
    R = QDialogButtonBox.ButtonRole
    return role in (R.RejectRole, R.NoRole)


def mark_safe_buttons(window) -> None:
    """Mark, as the window is shown, every button that must NOT be drawn as
    the main action even when it is the default:

    * a button-box REJECT or NO button (Cancel, No, Close, Keep, Go back). A
      destructive question keeps it as its default on purpose (Return must
      not delete), and it is not the main action;
    * every button that is not coloured in a window that ALREADY colours one
      or more (``#primary``, or :func:`mark_coloured`). Basti, 2026-09-25: a
      window or pop-up that already has coloured buttons keeps them exactly as
      they are; only a window with none gets its default filled. (Where the
      coloured button is not the one Return presses, the window is listed for
      Knut, K44, and not changed.)

    Synchronous on Show, so the first frame is already right. Only a mark:
    the look changes only if that button is, or becomes, the default.
    """
    from PyQt6.QtWidgets import QPushButton
    try:
        mine = [b for b in window.findChildren(QPushButton)
                if b.window() is window]
    except RuntimeError:
        return
    has_coloured = any(is_coloured(b) and not b.isHidden() for b in mine)
    for b in mine:
        safe = _role_is_safe(b) or (has_coloured and not is_coloured(b))
        if bool(b.property(SAFE_DEFAULT)) != safe:
            b.setProperty(SAFE_DEFAULT, safe)
            # A property selector is read when the button is polished, and it
            # was polished before its window's Show: polish it again.
            st = b.style()
            if st is not None:
                st.unpolish(b)
                st.polish(b)
            b.update()


def freeze_default(window) -> None:
    """Take ``autoDefault`` off every QPushButton of *window* that is not its
    default, so the default (and its fill) no longer moves with focus.

    Run AFTER Qt has settled the default for a shown dialog: a QDialog with no
    explicit default makes the first ``autoDefault`` button it meets the
    default as it is shown, and that is kept (Return keeps pressing what it
    pressed); only the moving-with-focus is taken away. A button focused at
    that moment is its own temporary default, so this runs after
    :func:`ui.widgets.defer_clear_button_focus` has dropped button focus.
    """
    from PyQt6.QtWidgets import QPushButton
    try:
        for b in window.findChildren(QPushButton):
            if b.window() is window and not b.isDefault():
                b.setAutoDefault(False)
    except RuntimeError:        # the window went away before the pass ran
        pass
