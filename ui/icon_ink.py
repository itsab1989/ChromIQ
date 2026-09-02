"""What a shipped icon becomes in a theme that has no colour.

**THE PROBLEM THIS SOLVES.** Most of ChromIQ's marks are drawn in code, so a
theme can reach them: the ⓘ ring, the load-chart glyphs, the Profile-run bar,
the pictograms. Five are not. The masthead's Open Project, Open Chart File,
Close Project and Tools marks are SVG files with their colours baked in, and
they ship as a matched light/dark pair because the artwork itself differs
between the two grounds -- not merely its tint. On a light-grey ground the app
picks the light pair, which is the right ARTWORK and the wrong PALETTE: the
patch dots stay magenta, amber and cyan, and the toolbox keeps its three
coloured bars.

The owner, looking at the shipped Neutral build:

    "tools icon, open project, open chart, close project icon still colored"

**WHY THE COLOUR IS DROPPED HERE AND NOT IN A THIRD SET OF FILES.** A hand-drawn
neutral variant of each asset would be four more files to keep in step with two
existing ones, and every future icon would owe a third drawing. The hue is not
what those files are FOR -- the shapes are. So the shapes are kept and the
palette is replaced, once, for any asset.

**WHY THE SVG SOURCE AND NOT THE RENDERED PIXMAP.** Recolouring the pixmap has
to guess what an antialiased edge pixel was a blend OF, and gets it wrong at
exactly the size these are seen at: a half-covered pixel on the rim of a 4 px
dot is still saturated enough to be called "accent" and comes out solid, which
fattens every dot and roughens every curve. Substituting in the source instead
lets Qt rasterise colours that are already neutral, so the edges are as clean as
they were and the mark is crisp at any device pixel ratio.

**THE RULE.** An icon in this theme is drawn in the theme's one ink, on the
theme's paper. Applied to a shipped asset's palette that is:

* a NEAR-WHITE source colour is PAPER and stays exactly as it is, so a page
  still reads as a sheet rather than as a filled block;
* every other source colour is INK and becomes ``NM_ACTION`` -- the patch dots,
  the toolbox bars, the close badge, and the outlines that carry them.

The outlines were the interesting half. Left as a darkened grey they are
1.28:1 to 2.0:1 on the Neutral masthead, where Rule 3 says that low a contrast
means "disabled" and nothing else, and the Tools toolbox -- which is nothing
BUT its outline -- then sat lighter than the settings sliders and the "?" it
shares a row with. See :func:`neutral_colour`.

**LIGHT AND DARK DO NOT MOVE.** :func:`svg_renderer` in any appearance but
Neutral returns exactly ``QSvgRenderer(str(path))`` -- the same object built
from the same file, no substitution attempted and no bytes read -- so the two
shipped appearances cannot be affected by anything in this module. That is
proved by hashing grabbed windows, not by reading this paragraph.
"""
from __future__ import annotations

import re

from PyQt6.QtGui import QColor

from ui import neutral_styles

#: At or above this luminance a source colour is PAPER and is left exactly as
#: it is, so a page still reads as a sheet rather than as a filled block. The
#: assets' paper is ``#fafafa`` (250) and the knockout inside the close badge is
#: ``#ffffff``; their next-lightest tone is the ``#c8c4be`` outline at 196, so
#: there is a wide gap to sit in and nothing lands near the line.
PAPER_LUMA = 235

#: Every way a colour can be written in the assets this touches. Hex only: the
#: files are exports and use ``#rgb`` / ``#rrggbb`` throughout. ``none``,
#: ``currentColor`` and gradient references are left exactly as they are -- an
#: unrecognised value is not a colour this module has an opinion about.
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")


def _luma(c: QColor) -> float:
    """Rec. 709 relative luminance, 0-255 -- how light this colour is, weighted
    the way an eye weights it. Used only to tell paper from ink."""
    return 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()


def neutral_colour(value: str) -> str:
    """The Neutral form of one source colour.

    **Two outcomes, and the second one is the owner's.** Paper stays paper;
    everything else -- outline, patch dot, toolbox bar, close badge -- becomes
    ``NM_ACTION``. It is the same answer :func:`ui.widgets.load_folder_icon`
    already gives the folder glyphs, and it makes an icon's ink the theme's one
    ink.

    IT WAS NOT ALWAYS THIS. The first draft kept each tone's ORDER and merely
    darkened it, which put the toolbox outline on ``#8d8d8d``. That is 2.0:1 on
    the masthead, and beside it sit the settings sliders and the "?" at
    ``NM_ACTION``, 15.96:1 -- so the Tools icon was the one mark in the group
    drawn in a lighter value than its neighbours. The owner, on that build:

        "the agent working on the icons should make the outline of the tools
        icon darker"

    Measured against the two icons it sits between, he is describing a real
    difference and not a preference. The fix is the VALUE and not the stroke
    weight: rendered at five values from ``#8d8d8d`` to ``NM_ACTION``, the
    toolbox only stops reading lighter than the "?" when it reaches ACTION,
    and the artwork's own stroke width already matches its neighbours there.
    ``NM_ACTION`` is the theme's darkest working value, so there is nowhere
    further to go and nothing new to invent.
    """
    c = QColor(value)
    if not c.isValid():
        return value
    if _luma(c) >= PAPER_LUMA:
        return value
    return neutral_styles.NM_ACTION


def neutral_svg(text: str) -> str:
    """An SVG document with every colour it names put through
    :func:`neutral_colour`."""
    return _HEX.sub(lambda m: neutral_colour(m.group(0)), text)


def svg_renderer(path, mode: "str | None" = None):
    """A ``QSvgRenderer`` for *path*, neutralised when the appearance asks.

    ``mode`` is the appearance NAME when the caller has one -- a component that
    was handed one by ``set_appearance`` knows which appearance it is painting
    into even before the application palette agrees. Left out, the live palette
    answers.

    Outside Neutral this is ``QSvgRenderer(str(path))`` and nothing else
    happens, so no shipped pixel can move. A file that cannot be read falls back
    to the same call rather than failing: an icon in the wrong palette is a
    fault, and no icon at all is a worse one.
    """
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtSvg import QSvgRenderer
    from ui.index_rule import use_index_rule

    if not use_index_rule(mode):
        return QSvgRenderer(str(path))
    try:
        text = open(str(path), "r", encoding="utf-8").read()
    except OSError:
        return QSvgRenderer(str(path))
    return QSvgRenderer(QByteArray(neutral_svg(text).encode("utf-8")))
