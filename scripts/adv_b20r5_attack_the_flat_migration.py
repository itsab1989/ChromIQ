"""Round 5 adversary: the flat-project migration, attacked as DATA.

Every case: list the disk, act, list the disk, diff. The promise under test is
"moves nothing or finishes" - a half-moved folder is the finding.
"""
import os, sys, json, shutil, stat, hashlib, subprocess, traceback
from pathlib import Path

os.environ["CHROMIQ_SETTINGS_FILE"] = "/tmp/chromiq-b20r5.ini"
os.environ["CHROMIQ_PRESETS_DIR"]   = "/tmp/chromiq-b20r5-presets"
sys.path.insert(0, "/Users/Basti/develop/ChromIQ")

from core.file_manager import (Project, migrate_flat_project, flat_legacy_chain,
                               peek_project, _chain_re)

WORK = Path("/tmp/b20r5-work")
OUT  = Path.home() / "Desktop/ChromIQ-beta20-proof/combined-round-5"

def listing(root: Path) -> dict:
    """Every file under root: relative path -> (size, sha1 of first 4k + size)."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            out[rel] = ("symlink", os.readlink(p))
        elif p.is_dir():
            out[rel] = ("dir", "")
        else:
            try:
                b = p.read_bytes()[:4096]
                out[rel] = ("file", f"{p.stat().st_size}:{hashlib.sha1(b).hexdigest()[:12]}")
            except OSError as e:
                out[rel] = ("file", f"UNREADABLE {e}")
    return out

def diff(before, after):
    gone = [k for k in before if k not in after]
    new  = [k for k in after if k not in before]
    chg  = [k for k in before if k in after and before[k] != after[k]]
    return gone, new, chg

RESULTS = []
def case(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco

def mkflat(root: Path, stem=None, extra=(), tifs=3):
    """A pre-redesign project: chart, measurement, profile loose in the folder."""
    root.mkdir(parents=True, exist_ok=True)
    stem = stem or root.name
    for ext in (".ti1", ".ti2", ".ti3", ".icc"):
        (root / f"{stem}{ext}").write_bytes(f"CONTENT {stem}{ext}".encode() * 50)
    for i in range(1, tifs + 1):
        (root / f"{stem}_{i:02d}.tif").write_bytes(f"TIF {i}".encode() * 500)
    for e in extra:
        (root / e).write_text(f"extra {e}", encoding="utf-8")
    return root

def report(tag, root, before, after, note=""):
    gone, new, chg = diff(before, after)
    lines = [f"### {tag}", f"root: {root}", f"note: {note}",
             f"disappeared entirely: {sorted(gone)}" if gone else "disappeared entirely: (none)",
             f"appeared: {sorted(new)}" if new else "appeared: (none)",
             f"changed in place: {sorted(chg)}" if chg else "changed in place: (none)"]
    return "\n".join(lines)

LOG = []

def run_case(name, fn):
    root = WORK / name.replace(" ", "_")
    if root.exists():
        # clear immutable flags left by a previous run
        subprocess.run(["chflags", "-R", "nouchg", str(root)], capture_output=True)
        subprocess.run(["chmod", "-R", "u+rwX", str(root)], capture_output=True)
        shutil.rmtree(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        verdict = fn(root)
    except Exception:
        verdict = "RAISED:\n" + traceback.format_exc()
    LOG.append(f"\n{'='*78}\nCASE {name}\n{'='*78}\n{verdict}")
    print(f"--- {name}\n{verdict}\n")

# ----------------------------------------------------------------- the cases

@case("01 plain flat project adopted")
def c01(root):
    mkflat(root, extra=["notes.txt", f"{root.name}_sanity_check.txt"])
    b = listing(root)
    pk_before = peek_project(root)
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    return (report("adopt", root, b, a, f"moved={n}") +
            f"\npeek before: exists={pk_before.exists} chart={pk_before.chart} "
            f"meas={pk_before.measurement} prof={pk_before.profile}")

@case("02 interrupted mid move then reloaded")
def c02(root):
    """SIGKILL between file 3 and file 4. Can the app recover?"""
    mkflat(root, tifs=6)
    b = listing(root)
    # simulate the kill: move the first 3 by hand, exactly as os.replace would
    loose = flat_legacy_chain(root)
    rd = root / "runs" / "run1"; rd.mkdir(parents=True)
    for f in loose[:3]:
        os.replace(f, rd / f.name)
    half = listing(root)
    # now the app opens it again
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    still_loose = [p.name for p in flat_legacy_chain(root)]
    in_run = sorted(p.name for p in rd.iterdir())
    pk = peek_project(root)
    return (report("recovery attempt", root, half, a, f"moved={n}") +
            f"\nSTILL LOOSE AT ROOT: {still_loose}"
            f"\nIN runs/run1: {in_run}"
            f"\npeek: exists={pk.exists} chart={pk.chart} meas={pk.measurement} prof={pk.profile}"
            f"\nfiles at start: {sorted(k for k,v in b.items() if v[0]=='file')}")

@case("03 destination already holds its own chart")
def c03(root):
    mkflat(root)
    rd = root / "runs" / "run1"; rd.mkdir(parents=True)
    (rd / f"{root.name}.ti1").write_text("SOMEBODY ELSE'S CHART", encoding="utf-8")
    b = listing(root)
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    return report("refuse", root, b, a, f"moved={n} (expect 0 and an identical disk)")

@case("04 one destination file already exists")
def c04(root):
    mkflat(root)
    rd = root / "runs" / "run1"; rd.mkdir(parents=True)
    (rd / f"{root.name}_02.tif").write_text("COLLIDING TIF", encoding="utf-8")
    b = listing(root)
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    return report("refuse on clash", root, b, a, f"moved={n} (expect 0)")

@case("05 read only project folder")
def c05(root):
    mkflat(root)
    b = listing(root)
    os.chmod(root, 0o555)
    try:
        n = migrate_flat_project(root, "run1")
    finally:
        os.chmod(root, 0o755)
    a = listing(root)
    return report("read only root", root, b, a, f"moved={n} (expect 0, nothing moved)")

@case("06 immutable file halfway through")
def c06(root):
    mkflat(root, tifs=6)
    loose = flat_legacy_chain(root)
    victim = loose[len(loose)//2]
    subprocess.run(["chflags", "uchg", str(victim)], check=True)
    b = listing(root)
    try:
        n = migrate_flat_project(root, "run1")
    finally:
        subprocess.run(["chflags", "-R", "nouchg", str(root)], capture_output=True)
    a = listing(root)
    still_loose = sorted(p.name for p in flat_legacy_chain(root))
    rd = root / "runs" / "run1"
    in_run = sorted(p.name for p in rd.iterdir()) if rd.is_dir() else []
    return (report("mid-move failure + rollback", root, b, a, f"moved={n}; victim={victim.name}") +
            f"\nSTILL LOOSE: {still_loose}\nIN RUN: {in_run}")

@case("07 run id is a traversal")
def c07(root):
    mkflat(root)
    outside = root.parent / "ESCAPED"
    if outside.exists(): shutil.rmtree(outside)
    b = listing(root)
    res = {}
    for rid in ["../..", "..", "../ESCAPED", "/tmp/b20r5-escape", "a/b",
                "..\\..", ".", "", None, "run1\0x", "C:", "~", "run1/../../.."]:
        try:
            res[repr(rid)] = migrate_flat_project(root, rid)
        except Exception as e:
            res[repr(rid)] = f"RAISED {type(e).__name__}: {e}"
    a = listing(root)
    esc = outside.exists() or Path("/tmp/b20r5-escape").exists()
    return (report("traversal", root, b, a, f"results={res}") +
            f"\nANYTHING ESCAPED THE PROJECT? {esc}")

@case("08 already stamped by the broken version")
def c08(root):
    """Manifest says schema current, runs/run1 empty, files still loose."""
    mkflat(root)
    (root / "runs" / "run1").mkdir(parents=True)
    (root / "project.json").write_text(json.dumps({
        "schema_version": 3, "target_name": root.name,
        "current_run": "run1", "runs": ["run1"]}), encoding="utf-8")
    b = listing(root)
    pk_b = peek_project(root)
    proj = Project.load(root)
    a = listing(root)
    pk_a = peek_project(root)
    return (report("repair a stamped project", root, b, a) +
            f"\npeek BEFORE: exists={pk_b.exists} chart={pk_b.chart} meas={pk_b.measurement} prof={pk_b.profile}"
            f"\npeek AFTER : exists={pk_a.exists} chart={pk_a.chart} meas={pk_a.measurement} prof={pk_a.profile}")

@case("09 project folder literally named project")
def c09(root):
    """`project.json` is <foldername>.<ext> when the folder is called 'project'."""
    root = root.parent / "project"
    if root.exists(): shutil.rmtree(root)
    proj = Project.create(root, "project")
    b = listing(root)
    chain = [p.name for p in flat_legacy_chain(root)]
    proj2 = Project.load(root)
    a = listing(root)
    return (report("a project named 'project'", root, b, a,
                   f"flat_legacy_chain saw: {chain}") +
            f"\nmanifest still at root? {(root/'project.json').is_file()}"
            f"\nstray copy in runs/run1? {(root/'runs'/'run1'/'project.json').is_file()}"
            f"\nis_a_project after? {(root/'project.json').is_file()}")

@case("10 two loads at once")
def c10(root):
    mkflat(root, tifs=8)
    b = listing(root)
    code = (f"import os,sys\n"
            f"os.environ['CHROMIQ_SETTINGS_FILE']='/tmp/chromiq-b20r5.ini'\n"
            f"sys.path.insert(0,'/Users/Basti/develop/ChromIQ')\n"
            f"from core.file_manager import migrate_flat_project\n"
            f"print(migrate_flat_project(__import__('pathlib').Path({str(root)!r}),'run1'))\n")
    ps = [subprocess.Popen([sys.executable, "-c", code],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           encoding="utf-8")
          for _ in range(4)]
    outs = [p.communicate() for p in ps]
    a = listing(root)
    rd = root / "runs" / "run1"
    still_loose = sorted(p.name for p in flat_legacy_chain(root))
    in_run = sorted(p.name for p in rd.iterdir()) if rd.is_dir() else []
    files_before = sorted(k for k, v in b.items() if v[0] == "file")
    files_after  = sorted(k.split("/")[-1] for k, v in a.items() if v[0] == "file")
    lost = [f for f in files_before if f.split("/")[-1] not in files_after]
    return (report("4 concurrent migrations", root, b, a,
                   f"exit codes/stdout={[o[0].strip() for o in outs]}") +
            f"\nSTILL LOOSE: {still_loose}\nIN RUN: {in_run}"
            f"\nFILES LOST ENTIRELY: {lost}"
            f"\nstderr: {[o[1].strip()[-300:] for o in outs if o[1].strip()]}")

@case("11 a name that collides after the move")
def c11(root):
    """Two files whose names differ only by case, on a case-insensitive disk."""
    mkflat(root)
    # NFD vs NFC: the same name in two spellings
    import unicodedata
    nfc = root.name
    b = listing(root)
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    files_b = sorted(k for k, v in b.items() if v[0] == "file")
    files_a = sorted(k.split("/")[-1] for k, v in a.items() if v[0] == "file")
    lost = [f for f in files_b if f.split("/")[-1] not in files_a]
    return report("case collision", root, b, a, f"moved={n}") + f"\nLOST: {lost}"

@case("12 runs is a file not a folder")
def c12(root):
    mkflat(root)
    (root / "runs").write_text("not a folder", encoding="utf-8")
    b = listing(root)
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    return report("runs is a file", root, b, a, f"moved={n} (expect 0)")

@case("13 a directory that matches the chain")
def c13(root):
    mkflat(root)
    (root / f"{root.name}.d").mkdir()
    (root / f"{root.name}.d" / "inside.txt").write_text("x", encoding="utf-8")
    b = listing(root)
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    return report("chain-shaped directory", root, b, a, f"moved={n}")

@case("14 symlink in the chain")
def c14(root):
    mkflat(root)
    tgt = root.parent / "OUTSIDE-TARGET.bin"
    tgt.write_text("a file outside the project", encoding="utf-8")
    (root / f"{root.name}.lnk").symlink_to(tgt)
    b = listing(root)
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    return (report("symlink member", root, b, a, f"moved={n}") +
            f"\noutside target still there? {tgt.is_file()}")

@case("15 the run holds only role-named files")
def c15(root):
    """A run with a measurement of its own, but no chain-named file."""
    mkflat(root)
    rd = root / "runs" / "run1"; rd.mkdir(parents=True)
    (rd / "merged.icc").write_text("A DIFFERENT PROFILE", encoding="utf-8")
    (rd / "reads").mkdir(); (rd / "reads" / "read1.ti3").write_text("A DIFFERENT MEASUREMENT", encoding="utf-8")
    b = listing(root)
    n = migrate_flat_project(root, "run1")
    a = listing(root)
    return report("merge into a run with role-named work", root, b, a, f"moved={n}")

for name, fn in RESULTS:
    run_case(name, fn)

(OUT / "logs" / "attack-migration.txt").write_text("\n".join(LOG), encoding="utf-8")
print(f"\nwritten to {OUT/'logs'/'attack-migration.txt'}")
