"""Before an Install button copies a profile into the profile folder.

Knut, #182 6102031563, answer 3 ("Installing replaces an installed profile of
the same name without asking. Should ChromIQ ask first?"): "Yes. Ask if user
wants to replace existing or cancel to rename the profile before trying to
install it again."

Every Install button (Build Profile, Apply Calibration, Check & Refine's
"Install Profile As Is", the scanner window) asks :func:`confirm_replace`
with the file the install would write, before it writes anything. The
window's words are M-PROFILE-INSTALL-REPLACE, which waits in §M-PROPOSED: a
window whose words nobody has approved is not shown (CLAUDE.md, the design
specifications are binding), so until it is approved an Install replaces the
installed profile exactly as it always has, and says so in ChromIQ's log.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.i18n import tr

log = logging.getLogger(__name__)


def confirm_replace(parent, dest: "Path | str") -> bool:
    """True when the install may go ahead and write *dest*.

    Nothing of that name installed: True, nothing asked. Otherwise the user
    is asked Replace / Cancel (Cancel the default, so a stray Return installs
    nothing), once the window's words are approved.
    """
    dest = Path(dest)
    try:
        exists = dest.exists()
    except OSError:
        exists = False
    if not exists:
        return True
    from workflow import measurement_messages as M
    msg = M.M_PROFILE_INSTALL_REPLACE
    if not msg.approved:
        log.info("%s is installed already and is replaced (the question "
                 "M-PROFILE-INSTALL-REPLACE waits for approval)", dest)
        return True
    from PyQt6.QtWidgets import QMessageBox

    from ui.widgets import fit_message_box_buttons
    title, body = msg.render(path=str(dest))
    box = QMessageBox(parent)
    box.setObjectName("profile_install_replace")
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body)
    replace = box.addButton(tr(M._INSTALL_REPLACE),
                            QMessageBox.ButtonRole.DestructiveRole)
    cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    fit_message_box_buttons(box)
    box.exec()
    ok = box.clickedButton() is replace
    log.info("%s is installed already: %s", dest,
             "replaced" if ok else "not installed (cancelled)")
    return ok
