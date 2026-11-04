"""Instructions beside ChromIQ's shared layout controls."""
from core.i18n import tr


def fd9_layout_note():
    """The note over Manual's layout panel while the FD-9 is selected. It says
    WHERE the four controls the FD-9 reads are, because they sit in the
    collapsed "Expert Options" group, and what each means for the FD-9,
    whose head travels across a row (review of #214, M6)."""
    return tr(
        "FD-9 (beta): an FD-9 chart has a fixed layout of its own, made for "
        "the way the FD-9 finds and reads the sheet. So most layout controls "
        "below are greyed, and they show the values an FD-9 chart really "
        "uses.\n\n"
        "What you can set for the FD-9 is under “Expert Options”, in "
        "“Patches & spacers”:\n"
        "  •  “Patch size”: the width × height of each patch, 6 to 30 mm "
        "each;\n"
        "  •  “Inter-patch gap”: the white gap between the rows of patches, "
        "along the way the sheet goes into the FD-9;\n"
        "  •  “Strip gap”: the white gap between the columns, across the "
        "sheet.\n"
        "Each gap can be 0 to 5 mm; 1 mm is the default and the one tested "
        "most. Choosing the FD-9 starts from its own defaults "
        "(Preferences > Chart Layout).\n\n"
        "Paper and Pages work as for any chart: when the chart has more "
        "patches than one sheet holds, it is printed on several numbered "
        "sheets. Feed each sheet into the FD-9 arrow first, with the printed "
        "side up.")
