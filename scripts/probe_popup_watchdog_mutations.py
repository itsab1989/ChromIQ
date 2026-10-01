"""Mutation probes for PopupWatchdog: each mutation is applied to a COPY of
scripts/onscreen_capture.py, the test file is run against the copy, and the
result must be RED. The repo file is never touched."""
import shutil, subprocess, sys, os
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
M = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__import__("tempfile").mkdtemp(prefix="chromiq-mut-"))
src = (REPO / "scripts/onscreen_capture.py").read_text(encoding="utf-8")
test = (REPO / "tests/test_a_driver_is_not_stuck_behind_a_popup.py").read_text(encoding="utf-8")
MUTS = {
 "dismiss does nothing": ('    def _dismiss(w) -> str:\n', '    def _dismiss(w) -> str:\n        return "mutated: nothing"\n'),
 "every modal counts as a question": ('        return isinstance(w, (QMessageBox, QInputDialog, QFileDialog))', '        return True'),
 "scripted rule never pressed": ('                    pressed = self._press(w, rule[1])', '                    pressed = False'),
 "grace ignored (dismiss at once, even scripted)": ('            if now - self._first_seen[key] < self.grace_s:\n                continue\n', ''),
 "report policy dismisses too": ('            if self.policy == "report":', '            if False:'),
 "fail policy never flags": ('                self.unexpected = True\n', '                pass\n'),
 "message boxes not looked for": ('            if isinstance(w, QMessageBox) and w.isVisible() and w not in found:', '            if False:'),
}
out = []
for name, (a, b) in MUTS.items():
    assert src.count(a) == 1, name
    d = M / name.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
    shutil.rmtree(d, ignore_errors=True); (d / "scripts").mkdir(parents=True); (d / "tests").mkdir()
    (d / "scripts/onscreen_capture.py").write_text(src.replace(a, b), encoding="utf-8")
    (d / "tests/test_mut.py").write_text(test.replace('Path(__file__).resolve().parent.parent / "scripts"', f'Path("{d}/scripts")'), encoding="utf-8")
    r = subprocess.run([str(REPO / ".venv/bin/python"), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "-o", "addopts=", "--timeout=60", str(d / "tests/test_mut.py")],
                       cwd=d, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    last = [l for l in r.stdout.splitlines() if l.strip()][-1]
    failed = [l.split("::")[-1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith("FAILED")]
    out.append(f"{'RED  ' if r.returncode else 'GREEN'} {name}: {last} {failed}")
print("\n".join(out))
