import os, sys, json, shutil, tempfile, pathlib
SBOX = tempfile.mkdtemp(prefix="r6-sandbox-")
os.environ["CHROMIQ_SETTINGS_FILE"] = os.path.join(SBOX, "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"]   = os.path.join(SBOX, "presets")
sys.path.insert(0, "/Users/Basti/develop/ChromIQ")
from pathlib import Path
from core.file_manager import (Project, migrate_flat_project, flat_legacy_chain,
                               is_a_plain_folder_name)

OUT = Path(os.path.expanduser("~/Desktop/ChromIQ-beta20-proof/combined-round-6"))
OUT.mkdir(parents=True, exist_ok=True)
report = []
def say(s=""):
    print(s); report.append(s)

def listing(root):
    """Every file under root, relative, with size. The comparison unit."""
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = p.stat().st_size
    return out

def build_flat(root: Path, stem: str):
    """A pre-runs project: chart, measurement, profile loose in the folder."""
    root.mkdir(parents=True, exist_ok=True)
    made = {}
    for ext, body in ((".ti1","TI1\n"), (".ti2","TI2\n"), (".ti3","TI3 DATA\n"),
                      (".icc","ICCPROFILE"), (".cht","CHT\n"), (".ps","PS\n")):
        (root / f"{stem}{ext}").write_text(body * 3, encoding="utf-8")
    (root / f"{stem}_01.tif").write_bytes(b"TIFFDATA"*4)
    return made

# ======================================================================
say("="*72); say("TASK 1 — fix 1: a project whose FOLDER name collides with its own files")
say("="*72)
task1_fail = []
CASES = [
    ("project",            "the headline case: folder name == manifest stem"),
    ("project_1",          "neighbour: matches the _NN branch of the chain"),
    ("Project",            "neighbour: case differs"),
    ("PROJECT",            "neighbour: upper case"),
    ("Where are my files", "the README trap"),
    ("runs",               "a folder named after the folder it migrates into"),
    ("mychart",            "control: a name matching a real chart stem"),
]
base = Path(tempfile.mkdtemp(prefix="r6-task1-"))
for name, why in CASES:
    root = base / name
    build_flat(root, name)
    before = listing(root)
    chain = [p.name for p in flat_legacy_chain(root)]

    # ---- FIRST open, through the real front door
    p1 = Project.create_or_load(root, name)
    after1 = listing(root)
    # ---- SECOND open: the reported symptom only appeared on the NEXT load
    p2 = Project.create_or_load(root, name)
    after2 = listing(root)

    manifest_stray = [k for k in after2 if k.endswith("project.json") and k != "project.json"]
    readme_stray   = [k for k in after2 if "Where are my files.txt" in k and k != "Where are my files.txt"]
    # every file that was loose must now be in runs/run1 (or cal/), none lost
    lost = [k for k in before if k not in after2 and f"runs/run1/{k}" not in after2]
    in_run = sorted(k for k in after2 if k.startswith("runs/run1/"))
    stable = after1 == after2

    ok = (not manifest_stray) and (not readme_stray) and (not lost) and stable
    say(f"\n--- {name!r}  ({why})")
    say(f"    chain seen by the mover : {chain}")
    say(f"    before  : {sorted(before)}")
    say(f"    after #2: {sorted(after2)}")
    say(f"    manifest stray in a run : {manifest_stray or 'none'}")
    say(f"    README   stray in a run : {readme_stray or 'none'}")
    say(f"    files lost              : {lost or 'none'}")
    say(f"    open#1 == open#2 on disk: {stable}")
    say(f"    VERDICT: {'PASS' if ok else 'FAIL'}")
    if not ok: task1_fail.append(name)

# ======================================================================
say("\n"+"="*72); say("TASK 2 — fix 2: attack is_a_plain_folder_name, and the disk after it")
say("="*72)
HOSTILE = [
    ("..",                       "parent"),
    (".",                        "self"),
    ("../..",                    "two up"),
    ("...",                      "all dots"),
    ("C:",                       "drive letter that collapses to runs/"),
    ("D:",                       "another drive entirely"),
    ("D:\\x",                    "drive + backslash"),
    ("\\\\server\\share",        "UNC prefix"),
    ("//server/share",           "UNC, forward slashes"),
    ("/etc",                     "absolute posix"),
    ("run1 ",                    "trailing space"),
    (" run1",                    "leading space"),
    ("run1.",                    "trailing dot"),
    ("x"*300,                    "300 characters"),
    ("CON",                      "reserved Windows device name"),
    ("NUL",                      "reserved Windows device name"),
    ("COM1",                     "reserved Windows device name"),
    ("",                         "empty string"),
    ("run\n1",                   "embedded newline"),
    ("run\x001",                 "embedded NUL"),
    (None,                       "None"),
    ("run1",                     "CONTROL — must be accepted"),
]
task2_fail = []
for value, why in HOSTILE:
    root = Path(tempfile.mkdtemp(prefix="r6-task2-")) / "proj"
    build_flat(root, "proj")
    before = listing(root)
    rule = is_a_plain_folder_name(value)
    n = migrate_flat_project(root, value)
    after = listing(root)
    # what escaped the project folder?
    escaped = sorted(str(p) for p in root.parent.rglob("*")
                     if p.is_file() and not str(p).startswith(str(root)+os.sep))
    untouched = (before == after)
    is_control = (value == "run1")
    if is_control:
        ok = rule and n == 7 and not escaped and all(k.startswith("runs/run1/") for k in after)
    else:
        # It must refuse (n==0) AND the disk must be byte-for-byte as found,
        # OR — for a name the rule allows — it must still land INSIDE runs/.
        contained = all(k.startswith("runs/") for k in after) if n else True
        ok = (not escaped) and ((n == 0 and untouched) or contained)
    say(f"\n--- current_run = {value!r:>22}  ({why})")
    say(f"    rule says plain : {rule}")
    say(f"    files moved     : {n}")
    say(f"    disk untouched  : {untouched}")
    if not untouched:
        say(f"    after           : {sorted(after)}")
    say(f"    escaped project : {escaped or 'nothing'}")
    say(f"    VERDICT: {'PASS' if ok else 'FAIL'}")
    if not ok: task2_fail.append(repr(value))

# ======================================================================
say("\n"+"="*72)
say(f"TASK 1 failures: {task1_fail or 'NONE'}")
say(f"TASK 2 failures: {task2_fail or 'NONE'}")
say("="*72)
(OUT / "probe_disk.txt").write_text("\n".join(report), encoding="utf-8")
print("\nwritten:", OUT / "probe_disk.txt")
sys.exit(1 if (task1_fail or task2_fail) else 0)
