"""Before/after screenshots of the window at several heights."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
from PyQt6.QtWidgets import QApplication, QMainWindow
from scanner_floor_probe import FakeSettings, dress_the_app, settle

lang, out_root, outdir, tag = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
Path(outdir).mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv[:1]); dress_the_app(app)
from core.i18n import set_language; set_language(lang)
from ui.dialogs.scanin_dialog import ScannerProfileDialog
scr = app.primaryScreen(); avail = scr.availableGeometry()
parent = QMainWindow(); parent.setGeometry(avail.x(), avail.y(), 1600, min(1000, avail.height()))
parent.show(); app.processEvents()
dlg = ScannerProfileDialog(object(), FakeSettings(out_root), parent)
dlg.show(); settle(app, dlg, 8)
fg = dlg.frameGeometry()
print(f"{lang} {tag}: opens {fg.width()}x{fg.height()} at ({fg.x()},{fg.y()}) "
      f"work area {avail.x()},{avail.y()} {avail.width()}x{avail.height()} "
      f"off-bottom={max(0, fg.bottom()-avail.bottom())} min={dlg.minimumWidth()}x{dlg.minimumHeight()}")
dlg.grab().save(f"{outdir}/{lang}-{tag}-asopened.png")
for h in (900, 800, 700, 640, 560, 480):
    dlg.setMinimumHeight(0)
    dlg.resize(dlg.width(), h)
    settle(app, dlg, 8)
    dlg.grab().save(f"{outdir}/{lang}-{tag}-h{h}.png")
    print(f"   h{h}: got {dlg.height()}, settings area min {dlg._scroll.minimumHeight()}")
