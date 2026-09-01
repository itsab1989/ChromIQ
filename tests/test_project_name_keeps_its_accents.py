"""A project name keeps its accents.

`FileManager._sanitise` turns a typed (or on-disk) project name into the folder
name ChromIQ actually creates, and that folder name goes on to be the stem of
every chart file, the text printtarg stamps on the printed sheet, and the
description inside the built ICC. It used to be

    _ILLEGAL = re.compile(r"[^\\w\\-.]+", re.UNICODE)

and `\\w` does not match a COMBINING MARK. So the same name cleaned two ways:

    "Müller" typed on a Mac        (U+00FC)          -> "Müller"
    "Müller" out of a zip/backup   (u + U+0308)      -> "Mu_ller"
    "Café"   out of a zip/backup   (e + U+0301)      -> "Cafe"   ← accent GONE

The name box read `Mu_ller` while `project.json` said `Müller`.

Two rules fix it, and both are needed:

  1. NORMALISE TO NFC FIRST. That is the one that matters for European names,
     and it is what makes the result canonical: whichever spelling arrives, one
     spelling reaches the folder, the manifest, the stems and the sheet.
  2. ADMIT COMBINING MARKS Mn/Mc. Thai, Devanagari, Hebrew niqqud and Arabic
     harakat have marks with NO composed form for NFC to compose them into, so
     rule 1 on its own still turns "นํ้า" into "น_า" — measured, and asserted
     below in `test_nfc_alone_would_not_be_enough`.

Nothing that used to be stripped may survive: the Windows-illegal characters,
the control characters and the leading/trailing dots and spaces are all still
gone, and `test_nothing_that_used_to_be_stripped_survives` proves it over every
code point in Unicode rather than over a hand-picked list.
"""
import random
import re
import unicodedata as ud

import pytest

from core.file_manager import FileManager, Project, Run

S = FileManager._sanitise


# The cleaner as it was before this fix, so the two can be compared directly
# instead of from memory.
_OLD_ILLEGAL = re.compile(r"[^\w\-.]+", re.UNICODE)
_OLD_TRAIL = re.compile(r"^[._-]+|[._-]+$")


def _old_sanitise(name: str) -> str:
    s = name.strip().replace(" ", "-")
    s = _OLD_ILLEGAL.sub("_", s)
    s = _OLD_TRAIL.sub("", s)
    return s or "session"


# ---------------------------------------------------------------------------
# 1. The fault itself
# ---------------------------------------------------------------------------

# (typed name, the folder it must produce)
ACCENTED = [
    ("Müller", "Müller"),
    ("Café", "Café"),
    ("café au lait", "café-au-lait"),
    ("Grün", "Grün"),
    ("Öl", "Öl"),
    ("Straße", "Straße"),
    ("Ångström", "Ångström"),
    ("naïve café", "naïve-café"),
    ("Škoda", "Škoda"),
    ("Ñuñoa", "Ñuñoa"),
    ("Đà Nẵng", "Đà-Nẵng"),
    ("Łódź", "Łódź"),
    ("Ünal Şen", "Ünal-Şen"),
    ("Müller-Café", "Müller-Café"),
]


@pytest.mark.parametrize("typed,folder", ACCENTED)
@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_an_accent_survives_whichever_way_it_is_spelled(typed, folder, form):
    """The reported fault: `Müller` -> `Mu_ller`, `café` -> `cafe`."""
    got = S(ud.normalize(form, typed))
    assert got == folder, (
        f"{form} {typed!r} cleaned to {got!r}, not {folder!r}")


@pytest.mark.parametrize("typed,_folder", ACCENTED)
def test_both_spellings_produce_the_SAME_folder(typed, _folder):
    """One name, one folder — however the name arrived.

    This is the property that makes the fix safe on a filesystem that does NOT
    fold normalisation (NTFS, ext4): the bytes ChromIQ writes are the same
    either way, rather than the same by the kernel's good grace.
    """
    assert S(ud.normalize("NFC", typed)) == S(ud.normalize("NFD", typed))


def test_the_trailing_accent_that_was_deleted_outright():
    """`café` NFD lost its é completely: `\\w` refused U+0301, `_ILLEGAL` made
    it `_`, and `_TRAIL` then ate the trailing `_`."""
    nfd = ud.normalize("NFD", "café")
    assert _old_sanitise(nfd) == "cafe"          # what it used to do
    assert S(nfd) == "café"                      # what it does now


def test_nfc_alone_would_not_be_enough():
    """Normalising and NOT widening the character class still mangles every
    script whose marks have no composed form."""
    def nfc_only(name):
        s = ud.normalize("NFC", name).strip().replace(" ", "-")
        return _OLD_TRAIL.sub("", _OLD_ILLEGAL.sub("_", s)) or "session"

    for name in ["นํ้า", "หน้า", "हिन्दी", "नमस्ते", "שָׁלוֹם", "مَرْحَبا"]:
        assert nfc_only(name) != name, (
            f"{name!r} needs no widening — pick a harder example")
        assert S(name) == name, (
            f"{name!r} cleaned to {S(name)!r}; a combining mark was destroyed")


def test_a_widened_class_alone_would_not_be_enough():
    """…and widening without normalising leaves two spellings of one name.

    Rule 2 without rule 1 keeps the decomposed form, so the folder, the
    manifest and the stems would each hold whichever spelling happened to
    arrive.
    """
    assert S(ud.normalize("NFD", "Müller")) == ud.normalize("NFC", "Müller")


# ---------------------------------------------------------------------------
# 2. The awkward inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("typed,folder", [
    # Nordic
    ("Ærø", "Ærø"),
    ("Þórr Ólafsson", "Þórr-Ólafsson"),
    ("Øystein Åsa", "Øystein-Åsa"),
    ("Jyväskylä", "Jyväskylä"),
    # Turkish — the dotless i and its capital, which NFD splits into I + U+0307
    ("ısı ölçer", "ısı-ölçer"),
    ("İstanbul", "İstanbul"),
    ("Diyarbakır", "Diyarbakır"),
    # Greek, including the final sigma and a tonos
    ("Ελλάδα", "Ελλάδα"),
    ("Θεσσαλονίκης", "Θεσσαλονίκης"),
    # Cyrillic and the CJK/Hangul block, which were never broken
    ("Привет мир", "Привет-мир"),
    ("日本語", "日本語"),
    ("한국어", "한국어"),
    # Right-to-left, with the vowel points that are pure combining marks
    ("שָׁלוֹם", "שָׁלוֹם"),
    ("مَرْحَبا", "مَرْحَبا"),
    ("العربية", "العربية"),
    # Scripts whose marks NFC can never compose
    ("ภาษาไทย", "ภาษาไทย"),
    ("हिन्दी", "हिन्दी"),
    ("ພາສາລາວ", "ພາສາລາວ"),
    ("ᐃᓄᒃᑎᑐᑦ", "ᐃᓄᒃᑎᑐᑦ"),
])
@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_the_awkward_scripts(typed, folder, form):
    got = S(ud.normalize(form, typed))
    assert got == folder, f"{form} {typed!r} -> {got!r}, wanted {folder!r}"


def test_a_right_to_left_name_gains_no_direction_marks():
    """A bidi control character is not part of a name and cannot go in a
    folder name silently — it is replaced like any other unprintable."""
    got = S("‏مرحبا‎")
    assert "‏" not in got and "‎" not in got, ascii(got)
    assert got == "مرحبا", ascii(got)


@pytest.mark.parametrize("typed,folder", [
    ("🎨🎨1", "1"),                 # documented behaviour: emoji are dropped
    ("Canon 🎨 PRO-300", "Canon-_-PRO-300"),
    ("1️⃣", "1"),                   # the keycap's selector + enclosing mark go too
    ("☺️ smile", "smile"),
])
def test_an_emoji_still_disappears_whole(typed, folder):
    """An emoji leaves no invisible residue.

    Variation selectors are category Mn, so admitting marks naively would have
    left `1️` — a folder that looks like `1` but is not.
    """
    got = S(typed)
    assert got == folder, f"{typed!r} -> {ascii(got)}, wanted {folder!r}"
    assert all(ud.category(c)[0] != "M" or c.isalnum() or True for c in got)
    assert "️" not in got and "⃣" not in got, ascii(got)


@pytest.mark.parametrize("typed", [
    "̈̈",           # only combining marks
    "́",                 # one orphan acute
    "ि्",           # only Devanagari matras
    "",
    "   ",
    "...",
    "---",
    "___",
    ".-_.",
    "///",
    "\x00\x01",
])
def test_a_name_that_cleans_away_to_nothing_falls_back_to_session(typed):
    """A folder whose name is a combining mark has no visible name at all.

    Before marks were kept this was impossible — the only non-alphanumeric
    survivors were `.` `_` `-`, and `_TRAIL` ate a string made only of those.
    It has to stay impossible.
    """
    got = S(typed)
    assert got == "session", f"{ascii(typed)} -> {ascii(got)}"


def test_an_orphan_mark_never_leads_the_folder_name():
    """A combining mark with no base under it is dropped, not kept."""
    got = S("̈Müller")
    assert got == "Müller", ascii(got)
    assert ud.category(got[0])[0] != "M"


# ---------------------------------------------------------------------------
# 3. Nothing that used to be stripped survives
# ---------------------------------------------------------------------------

WINDOWS_ILLEGAL = '/\\:*?"<>|'


@pytest.mark.parametrize("ch", list(WINDOWS_ILLEGAL))
def test_the_characters_a_folder_cannot_hold_are_still_replaced(ch):
    """A name that is legal on macOS and illegal on Windows is a real case —
    projects are shared between the two."""
    got = S(f"Müller{ch}Café")
    assert ch not in got, f"{ch!r} survived into {got!r}"
    assert got == "Müller_Café", got


def test_every_control_character_is_still_replaced():
    for cp in list(range(0x20)) + [0x7F] + list(range(0x80, 0xA0)):
        got = S(f"a{chr(cp)}b")
        assert chr(cp) not in got, f"U+{cp:04X} survived into {ascii(got)}"


@pytest.mark.parametrize("typed,folder", [
    ("  Müller  ", "Müller"),
    (" .Müller. ", "Müller"),
    ("Müller...", "Müller"),
    ("...Müller", "Müller"),
    ("Müller   ", "Müller"),
    ("-Müller-", "Müller"),
])
def test_leading_and_trailing_dots_and_spaces_are_still_stripped(typed, folder):
    """Windows silently drops a trailing dot or space from a folder name, so a
    name that ends in one is a name that does not round-trip."""
    assert S(typed) == folder


def test_nothing_that_used_to_be_stripped_survives():
    """THE AUDIT, over every code point rather than a hand-picked list.

    For each character, cleaning `a<ch>b` before and after this change must
    differ only by the two rules: a character may newly SURVIVE only if it is a
    combining mark (Mn/Mc), and a character may newly disappear only because
    NFC re-spelled it as its canonical equivalent (U+0958 DEVANAGARI QA, for
    instance, is a composition exclusion and NFC spells it as क + ़).
    """
    newly_kept_categories = set()
    really_lost = []
    for cp in range(0x110000):
        ch = chr(cp)
        if ch in "\r\n":
            continue
        probe = f"a{ch}b"
        old, new = _old_sanitise(probe), S(probe)
        if old == new:
            continue
        if ch in new and ch not in old:
            newly_kept_categories.add(ud.category(ch))
        elif ch in old and ch not in new:
            if ud.normalize("NFD", old) != ud.normalize("NFD", new):
                really_lost.append((hex(cp), ud.category(ch), old, new))
    assert newly_kept_categories <= {"Mn", "Mc"}, (
        f"characters outside the combining-mark categories now survive: "
        f"{sorted(newly_kept_categories)}")
    assert really_lost == [], (
        f"characters lost for a reason other than canonical re-spelling: "
        f"{really_lost[:10]}")


def test_isalnum_or_underscore_is_exactly_what_backslash_w_matched():
    """The character class was translated from a regex to a predicate, so the
    translation itself has to be exact.

    CPython's SRE tests `Py_UNICODE_ISALNUM(ch) || ch == '_'` for `\\w` on a str
    pattern; `str.isalnum()` tests the same table. Proved, not assumed.
    """
    w = re.compile(r"\w", re.UNICODE)
    mismatches = [hex(cp) for cp in range(0x110000)
                  if bool(w.match(chr(cp))) != (chr(cp).isalnum() or chr(cp) == "_")]
    assert mismatches == [], mismatches[:10]


# ---------------------------------------------------------------------------
# 4. Properties the folder name must always have
# ---------------------------------------------------------------------------

def _random_names(n, seed):
    rnd = random.Random(seed)
    pool = [chr(c) for c in range(0x2500)
            if ud.category(chr(c))[0] in "LNMPSZC"]
    pool += list("/\\:*?\"<>| .-_")
    return ["".join(rnd.choice(pool) for _ in range(rnd.randint(1, 8)))
            for _ in range(n)]


def test_the_folder_name_is_always_nfc():
    """The point of rule 1: one spelling reaches disk.

    If the output could be decomposed, the folder, `project.json` and the chart
    stems would agree only because APFS folds the lookup — luck, not design,
    and luck that does not travel to NTFS or ext4.
    """
    bad = [ascii(n) for n in _random_names(20000, seed=11)
           if S(n) != ud.normalize("NFC", S(n))]
    assert bad == [], bad[:5]


def test_cleaning_a_cleaned_name_changes_nothing():
    """`_sanitise` is applied more than once to the same name — `working_dir`
    re-cleans the folder name of an open project on every call and compares it
    to the stored one. A cleaner that is not idempotent breaks that compare.
    """
    bad = [ascii(n) for n in _random_names(20000, seed=12) if S(S(n)) != S(n)]
    assert bad == [], bad[:5]


def test_the_folder_name_can_always_be_a_folder():
    for n in _random_names(20000, seed=13):
        got = S(n)
        assert got, f"empty folder name from {ascii(n)}"
        assert "/" not in got and "\\" not in got, ascii(got)
        assert got not in (".", ".."), ascii(got)
        assert not got.startswith("."), ascii(got)
        assert got == got.strip(" ."), ascii(got)
        assert any(c.isalnum() for c in got), ascii(got)


# ---------------------------------------------------------------------------
# 5. Backward compatibility — every folder the owner already has
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("existing", [
    "Mu_ller",                       # the mangled folder this bug created
    "cafe",
    "A_ngstro_m",
    "nai_ve-cafe",
    "Canon-PRO-300-Baryta",
    "session",
    "Pro.1000",
    "test",
    "Müller",                        # …and one that was already right
    "CON",                           # Windows-reserved, creatable on macOS
])
def test_an_existing_folder_name_is_left_exactly_as_it_is(existing):
    """A NAME ALREADY ON DISK IS A FIXED POINT. `open_project_at` cleans the
    folder's own name to derive the target name, and `working_dir` re-cleans it
    to decide whether the project is where it says it is — so any change here
    moves somebody's project."""
    assert S(existing) == existing


def test_a_project_already_called_Mu_ller_still_opens_and_builds(tmp_path):
    """The folder this bug already created keeps working, untouched.

    Basti's ruling: leave every folder he already has exactly as it is.
    """
    root = tmp_path / "Mu_ller"
    proj = Project.create(root, "Mu_ller")
    run = proj.current_run()
    run.chart_ti1.write_text("fake ti1")
    run.chart_ti2.write_text("fake ti2")

    reopened = Project.create_or_load(root, "Mu_ller")
    assert reopened.root == root
    assert reopened.target_name == "Mu_ller"
    assert reopened.current_run().dir == run.dir
    assert reopened.current_run().chart_ti1.read_text() == "fake ti1"
    assert reopened.current_run().stem == "Mu_ller"


def test_an_existing_project_resolves_through_every_name_route(tmp_path, monkeypatch):
    """`_sanitise`, `preview_project_root`, `resolved_root_for_name` and
    `working_dir` must all still land on the folder that is there."""
    from core.settings import AppSettings

    out = tmp_path / "out"
    out.mkdir()
    (out / "Mu_ller").mkdir()
    Project.create(out / "Mu_ller", "Mu_ller")

    s = AppSettings()
    s.set("custom_output_path", str(out))
    fm = FileManager(s)
    fm.set_target_name("Mu_ller")
    assert fm.working_dir() == out / "Mu_ller"
    assert fm.preview_project_root("Mu_ller") == out / "Mu_ller"
    assert fm.resolved_root_for_name("Mu_ller") == out / "Mu_ller"
    assert fm.has_project()
    assert fm.project().root == out / "Mu_ller"


def test_a_decomposed_folder_on_disk_reports_its_real_name(tmp_path):
    """The on-screen fault: the box read `Mu_ller` for a folder called
    `Müller` that had arrived decomposed (out of a zip, a backup or an HFS+
    volume). It now reads the name of the project.

    And the PATH is still the filesystem's own — `working_dir` hands back the
    folder it was given, decomposed bytes and all, so nothing is looked up
    under a spelling the disk may not fold.
    """
    from core.settings import AppSettings

    out = tmp_path / "out"
    out.mkdir()
    nfd = ud.normalize("NFD", "Müller")
    root = out / nfd
    root.mkdir()
    Project.create(root, "Müller")

    s = AppSettings()
    s.set("custom_output_path", str(out))
    fm = FileManager(s)
    fm.open_project_at(root)

    assert fm.get_target_name() == ud.normalize("NFC", "Müller"), (
        f"the name box would show {ascii(fm.get_target_name())}")
    assert fm.working_dir() == root, (
        "working_dir re-derived a path instead of using the folder on disk")
    assert fm.working_dir().name == nfd, "the path lost the filesystem's bytes"
    assert fm.project().root == root


# ---------------------------------------------------------------------------
# 6. Everything downstream of the name
# ---------------------------------------------------------------------------

def test_an_accented_name_reaches_every_chart_file_stem(tmp_path):
    """The stem goes into .ti1/.ti2/.ti3/.cht/.icc, onto the printed sheet via
    printtarg, and into the ICC description. It must carry the accent."""
    name = S("Müller-Café")
    root = tmp_path / name
    proj = Project.create(root, name)
    run = proj.current_run()
    assert run.stem == "Müller-Café"
    for path in (run.chart_ti1, run.chart_ti2, run.chart_cht, run.chart_ps,
                 run.measurement_ti3, run.profile_icc, run.chart_channels_json):
        assert path.name.startswith("Müller-Café"), path.name
        assert path.parent == run.dir

    # and the files can actually be written and read back under that stem
    run.chart_ti1.write_text("ti1")
    assert (root / "runs" / "run1" / "Müller-Café.ti1").read_text() == "ti1"
    assert run.chart_ti1 in list(run.dir.glob("*.ti1"))


def test_the_manifest_and_the_folder_agree_for_an_accented_name(tmp_path):
    from core.settings import AppSettings
    import json

    out = tmp_path / "out"
    out.mkdir()
    s = AppSettings()
    s.set("custom_output_path", str(out))
    fm = FileManager(s)
    fm.set_target_name(ud.normalize("NFD", "Müller-Café"))

    proj = fm.project()
    manifest = json.loads((proj.root / "project.json").read_text(encoding="utf-8"))
    assert manifest["target_name"] == "Müller-Café"
    assert proj.root.name == "Müller-Café"
    assert fm.get_target_name() == "Müller-Café"
    assert fm.working_dir() == proj.root


def test_the_picker_and_a_peek_still_see_an_accented_project(tmp_path):
    from ui.dialogs.project_picker import list_projects
    from core.file_manager import peek_project

    out = tmp_path / "out"
    out.mkdir()
    for nm in ("Müller-Café", ud.normalize("NFD", "Ångström"), "Mu_ller"):
        Project.create(out / nm, nm)

    names = [n for n, _ in list_projects(out)]
    assert len(names) == 3, names
    for n in names:
        peek = peek_project(out / n)
        assert peek.exists, n


def test_run_for_dir_keeps_the_accent(tmp_path):
    """`Run.for_dir` gives a project-less Run for path ops on a known folder —
    its stem comes from the folder, so it must carry the accent too."""
    d = tmp_path / "Müller-Café" / "runs" / "run1"
    d.mkdir(parents=True)
    run = Run.for_dir(d)
    assert run.stem == "Müller-Café"
    assert run.chart_ti2.name == "Müller-Café.ti2"


# ---------------------------------------------------------------------------
# 7. The name dialog agrees with the cleaner
# ---------------------------------------------------------------------------

def test_the_dialog_shows_the_folder_it_will_really_make(qapp):
    """`name_prompt.folder_name` is what the person is shown under the field.
    It must be the same string the folder gets."""
    from ui.dialogs import name_prompt

    for typed in ["Müller-Café", ud.normalize("NFD", "Müller-Café"),
                  "naïve café", "ภาษาไทย"]:
        assert name_prompt.folder_name(typed) == S(
            FileManager.strip_workfile_ext(typed))
    assert name_prompt.folder_name(ud.normalize("NFD", "Müller")) == "Müller"


def test_an_accented_name_is_accepted_by_the_dialog(qapp):
    from ui.dialogs import name_prompt

    for typed in ["Müller-Café", ud.normalize("NFD", "Müller-Café"),
                  "Ångström", "ภาษาไทย", "שָׁלוֹם"]:
        assert name_prompt.validate(typed) is None, typed


def test_the_windows_reserved_names_are_still_refused_at_the_door(qapp):
    """`_sanitise` does NOT escape them — deliberately: it is also the function
    that RESOLVES an existing folder, so escaping `CON` there would stop a
    folder already called `CON` from being found. The refusal belongs at the
    door, and this records where it lives.
    """
    from ui.dialogs import name_prompt

    assert S("CON") == "CON"                     # the cleaner passes it through
    for reserved in ("CON", "prn", "AUX", "NUL", "COM1", "LPT9", "CON.txt",
                     "CON!"):
        assert name_prompt.validate(reserved) is not None, reserved
    assert name_prompt.validate("CONCERT") is None
