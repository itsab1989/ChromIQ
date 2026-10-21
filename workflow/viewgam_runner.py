"""Runs viewgam to combine two gamut files and compute coverage statistics."""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from core.logger import get_logger

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)

_INTERSECT_RE   = re.compile(r"Intersecting volume\s*=\s*([\d.]+)")


# Structured error patterns for viewgam (Argyll 3.5.0 gamut/viewgam.c).
# Many error()s in viewgam are about per-field validation of the .gam files —
# we collapse them into a single "gamut file format" pattern.
_VIEWGAM_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L523 — most common: the two gamuts can't be compared
    (re.compile(r"Gamuts are not compatible!"),
     "gamuts_incompatible",
     "The two gamut files use different colour spaces or have incompatible "
     "centres — viewgam can't combine them. Make sure both gamuts were built "
     "from profiles in the same colour space (e.g. both RGB or both CMYK)."),
    # L364 — input file read error
    (re.compile(r"Input file '([^']+)' error\s*:\s*(.+)$"),
     "gam_read",
     "Could not read the gamut file '{0}'.\n\nArgyll reported: {1}"),
    # L514 / L517 — gamut load failure with no Argyll message
    (re.compile(r"Input file '([^']+)' read failed"),
     "gam_read_generic",
     "Could not load the gamut file '{0}'. The file may be corrupt or in an "
     "older format — re-export the gamut from the source ICC profile."),
    # L367 — wrong file type
    (re.compile(r"Input file isn't a GAMUT format file"),
     "wrong_filetype",
     "One of the selected files isn't a .gam file. Pick a gamut (.gam) file "
     "exported by iccgamut."),
    # L369 / L372 / L374 / L377-414 — corrupt / wrong-version .gam files
    (re.compile(r"Input file doesn't contain (?:exactly two tables|field \w+)|"
                r"No (?:vertices|triangles)|"
                r"Field \w+ is wrong type"),
     "gam_corrupt",
     "The gamut file is missing required data or has an unexpected format — "
     "regenerate it from the ICC profile."),
    # L347 / L497 — output file failures
    (re.compile(r"(?:Error creating|Closing) (?:.+) object '([^']+)'"),
     "output_write",
     "Could not write the combined gamut output to '{0}'. Check temp-folder "
     "writability."),
]

_VIEWGAM_WARNING_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # viewgam emits one user-facing warning (~L463) about non-LAB combinations.
    # Currently a generic catch — only surfaces if viewgam prints it verbatim.
    (re.compile(r"^Warning(?:\s*:\s*|\s+)(.+)$", re.IGNORECASE),
     "viewgam_warning",
     "{0}"),
]


# Colour remap moved to Python (see gamut_viewer._apply_chromiq_colors) —
# JS-side mutation didn't reliably propagate to X3DOM's GPU buffers after
# the scene was parsed via body-script init, so individual profile views
# showed default colours while the combined view (which gets a second
# setAttribute pass from _COMPARE_CONTROLS_JS at +150 ms) accidentally
# worked. The X3D Background still has to be JS-driven because it reads
# the CSS body background at runtime and needs to follow live theme swaps.
from workflow.gamut_viewer import _apply_chromiq_colors
from core.i18n import tr

_THEMED_JS = """\
(function () {
  function applyBackground() {
    var bgStr = window.getComputedStyle(document.body).backgroundColor;
    var m = bgStr.match(/rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
    if (!m) return;
    var sky = (+m[1]/255).toFixed(5) + ' '
            + (+m[2]/255).toFixed(5) + ' '
            + (+m[3]/255).toFixed(5);
    var scene = document.querySelector('scene');
    if (!scene) return;
    var bgNode = scene.querySelector('background');
    if (bgNode) {
      bgNode.setAttribute('skyColor', sky);
      bgNode.setAttribute('groundColor', sky);
    } else {
      bgNode = document.createElement('background');
      bgNode.setAttribute('skyColor', sky);
      bgNode.setAttribute('groundColor', sky);
      scene.insertBefore(bgNode, scene.firstChild);
    }
  }
  document.addEventListener('DOMContentLoaded', applyBackground);
  document.addEventListener('x3dom-initialized', function() { setTimeout(applyBackground, 50); });
})();
"""

_COVERAGE_RE    = re.compile(r"'[^']+' volume = ([\d.]+) cubic units, intersect = ([\d.]+)%")


_COMPARE_CONTROLS_JS = """\
(function () {
  function rgb2hsl(r, g, b) {
    var mx = Math.max(r,g,b), mn = Math.min(r,g,b), d = mx-mn;
    var l = (mx+mn)/2, h = 0, s = 0;
    if (d > 0) {
      s = l > 0.5 ? d/(2-mx-mn) : d/(mx+mn);
      if (mx===r)      h = ((g-b)/d + (g<b?6:0))/6;
      else if (mx===g) h = ((b-r)/d + 2)/6;
      else             h = ((r-g)/d + 4)/6;
    }
    return [h*360, s, l];
  }
  function hq(p, q, t) {
    if (t < 0) t += 1; if (t > 1) t -= 1;
    if (t < 1/6) return p+(q-p)*6*t;
    if (t < 0.5) return q;
    if (t < 2/3) return p+(q-p)*(2/3-t)*6;
    return p;
  }
  function hsl2rgb(h, s, l) {
    h /= 360;
    if (s === 0) return [l, l, l];
    var q = l<0.5 ? l*(1+s) : l+s-l*s, p = 2*l-q;
    return [hq(p,q,h+1/3), hq(p,q,h), hq(p,q,h-1/3)];
  }
  // A semi-transparent surface that still writes the depth buffer hides
  // whatever is behind it (you'd only see through it at full transparency).
  // Switch depth-writing off while a gamut is translucent so the other gamut
  // shows through it, and back on when it's fully opaque (crisp solid).
  //
  // N1 (Knut, 4.3.8-beta.3): BOTH halves of that only work through nodes the
  // page already holds. This x3dom (1.6.3) learns of a NEW element only from
  // the DOMNodeInserted event, which Chromium has removed, so a <DepthMode>
  // created here never reached the renderer and profile A kept writing depth
  // at every opacity: a smaller B inside it stayed hidden until A fell under
  // x3dom's alpha clip (0.1), "only below 10 %". The page is therefore built
  // with a <DepthMode> in every Appearance (_with_depth_modes) and this only
  // changes attributes, which x3dom does see. And x3dom sorts a shape into its
  // opaque or transparent pass ONCE, from the transparency it had on load, so
  // A (loaded opaque) was still drawn in the opaque pass. sortType is set
  // explicitly here so a translucent gamut is drawn after an opaque one.
  function setDepth(app, transparent) {
    var dm = app.querySelector('depthmode');
    if (dm && dm.getAttribute('enableDepthTest') !== 'false') {
      dm.setAttribute('readOnly', transparent ? 'true' : 'false');
    }
    app.setAttribute('sortType', transparent ? 'transparent' : 'opaque');
  }
  function applyTransparency() {
    var T = String(typeof window._chromiqCompareOpacity !== 'undefined'
                   ? window._chromiqCompareOpacity : 0.5);
    var g = document.getElementById('chromiq-compare');
    if (!g) return;
    g.querySelectorAll('material').forEach(function (m) {
      m.setAttribute('transparency', T);
    });
    g.querySelectorAll('appearance').forEach(function (app) {
      if (!app.querySelector('material')) {
        var m = document.createElement('material');
        m.setAttribute('transparency', T);
        app.appendChild(m);
      }
      setDepth(app, parseFloat(T) > 0.01);
    });
  }
  function applySaturation() {
    var S = typeof window._chromiqCompareSat !== 'undefined'
            ? window._chromiqCompareSat : 1.0;
    var g = document.getElementById('chromiq-compare');
    if (!g) return;
    g.querySelectorAll('color').forEach(function (c) {
      if (!c._origColors) c._origColors = c.getAttribute('color') || '';
      var parts = c._origColors.trim().split(/\\s+/), out = [];
      for (var i = 0; i + 2 < parts.length; i += 3) {
        var hsl = rgb2hsl(+parts[i], +parts[i+1], +parts[i+2]);
        var rgb = hsl2rgb(hsl[0], Math.min(1, hsl[1] * S), hsl[2]);
        out.push(rgb[0].toFixed(5), rgb[1].toFixed(5), rgb[2].toFixed(5));
      }
      c.setAttribute('color', out.join(' '));
    });
  }
  function applyAll() { applyTransparency(); applySaturation(); }
  window._chromiqApplyCompare = applyAll;

  // --- Primary (the colourful base gamut) — everything NOT in #chromiq-compare.
  // Lets the two gamuts carry independent opacity / saturation controls.
  function primaryEls(tag) {
    return Array.prototype.filter.call(
      document.querySelectorAll(tag),
      function (e) { return !e.closest('#chromiq-compare'); });
  }
  function applyPrimaryTransparency() {
    if (typeof window._chromiqPrimaryOpacity === 'undefined') return;
    var T = String(window._chromiqPrimaryOpacity);
    primaryEls('material').forEach(function (m) { m.setAttribute('transparency', T); });
    primaryEls('appearance').forEach(function (app) {
      if (!app.querySelector('material')) {
        var m = document.createElement('material');
        m.setAttribute('transparency', T);
        app.appendChild(m);
      }
      setDepth(app, parseFloat(T) > 0.01);
    });
  }
  function applyPrimarySaturation() {
    if (typeof window._chromiqPrimarySat === 'undefined') return;
    var S = window._chromiqPrimarySat;
    primaryEls('color').forEach(function (c) {
      if (!c._origColors) c._origColors = c.getAttribute('color') || '';
      var parts = c._origColors.trim().split(/\\s+/), out = [];
      for (var i = 0; i + 2 < parts.length; i += 3) {
        var hsl = rgb2hsl(+parts[i], +parts[i+1], +parts[i+2]);
        var rgb = hsl2rgb(hsl[0], Math.min(1, hsl[1] * S), hsl[2]);
        out.push(rgb[0].toFixed(5), rgb[1].toFixed(5), rgb[2].toFixed(5));
      }
      c.setAttribute('color', out.join(' '));
    });
  }
  function applyAllPrimary() { applyPrimaryTransparency(); applyPrimarySaturation(); }
  window._chromiqApplyPrimary = applyAllPrimary;

  // N1: this x3dom (1.6.3) never fires 'x3dom-initialized', and a value set
  // on an element before x3dom has built its node from it is lost. The panel
  // pushes its slider values when the page has loaded, which can be before
  // that, so a re-run analysis drew B at the page default (50 %) while its
  // slider said 100 %. Wait until x3dom holds the scene's materials, then
  // apply whatever the panel last asked for (or the defaults).
  function whenX3domReady(fn) {
    var tries = 0;
    (function poll() {
      var ms = document.querySelectorAll('material');
      var ready = ms.length > 0;
      for (var i = 0; ready && i < ms.length; i++) {
        if (!ms[i]._x3domNode) ready = false;
      }
      if (ready) { fn(); return; }
      if (++tries < 200) setTimeout(poll, 50);
    })();
  }
  function applyEverything() { applyAll(); applyAllPrimary(); }
  window._chromiqWhenReady = whenX3domReady;
  document.addEventListener('DOMContentLoaded', function () {
    whenX3domReady(applyEverything);
  });
  document.addEventListener('x3dom-initialized', function () {
    setTimeout(applyEverything, 150);
  });
})();
"""


def _add_material_transparency(mo: re.Match, value: float = 0.5) -> str:
    """Add or update the transparency attribute on a matched <Material .../> tag."""
    tag = mo.group(0)
    if re.search(r"\btransparency\s*=", tag, re.IGNORECASE):
        return re.sub(
            r'\btransparency\s*=\s*["\'][^"\']*["\']',
            f'transparency="{value}"',
            tag,
            flags=re.IGNORECASE,
        )
    return re.sub(r"\s*(/?>)$", rf' transparency="{value}"\1', tag)


_SCENE_DUPE_TAGS = ("Environment", "Background", "NavigationInfo",
                    "Viewpoint", "DirectionalLight", "PointLight", "SpotLight")


def _strip_scene_level_dupes(scene_content: str) -> str:
    """Remove the scene-level bindable / lighting / environment nodes
    iccgamut emits inside <Scene>. When the compare scene is merged into
    primary's as an overlay Group, these duplicate the equivalent nodes
    from primary's scene — most importantly the 6 DirectionalLight nodes,
    which double up and roughly double the illumination on every shape
    in the combined view, making both profiles look much brighter than
    they do alone. Strip them so only the gamut geometry (Transforms /
    Shapes) carries over.
    """
    for tag in _SCENE_DUPE_TAGS:
        pattern = re.compile(
            rf"<{tag}\b[^>]*?(?:/>|>.*?</{tag}>)\s*",
            re.DOTALL | re.IGNORECASE,
        )
        scene_content = pattern.sub("", scene_content)
    return scene_content


def _close_polys(coord_index: str) -> str:
    """Close each polygon in an IndexedFaceSet coordIndex so it draws as a full
    wireframe loop when reused as IndexedLineSet indices."""
    groups = []
    for grp in coord_index.split("-1"):
        idx = grp.split()
        if not idx:
            continue
        if idx[0] != idx[-1]:
            idx = idx + [idx[0]]      # close the loop (… → first vertex)
        groups.append(" ".join(idx))
    return (" -1 ".join(groups) + " -1") if groups else ""


def _to_wireframe(scene: str) -> str:
    """Turn every IndexedFaceSet in an X3D scene into an IndexedLineSet, so the
    gamut renders as a non-occluding wireframe cage (this x3dom build has no
    FillProperties, but does support IndexedLineSet). Filled faces are what
    hide an overlapping gamut; lines never do."""
    # Face-only attributes IndexedLineSet doesn't accept — leaving them on makes
    # x3dom reject the node and the whole scene goes blank.
    face_attrs = ("solid", "ccw", "convex", "creaseAngle",
                  "normalPerVertex", "normalIndex")

    def repl(m: "re.Match") -> str:
        attrs = m.group(1)
        # coordIndex: single OR double quotes, may span lines (Argyll wraps it).
        ci = re.search(r"coordIndex\s*=\s*(['\"])(.*?)\1", attrs,
                       re.IGNORECASE | re.DOTALL)
        if ci:
            attrs = (attrs[:ci.start()]
                     + f'coordIndex="{_close_polys(ci.group(2))}"'
                     + attrs[ci.end():])
        for a in face_attrs:
            attrs = re.sub(rf"\s*{a}\s*=\s*(['\"]).*?\1", "", attrs,
                           flags=re.IGNORECASE | re.DOTALL)
        return f"<IndexedLineSet{attrs}>"

    scene = re.sub(r"<IndexedFaceSet\b([^>]*)>", repl, scene,
                   flags=re.IGNORECASE | re.DOTALL)
    scene = re.sub(r"</IndexedFaceSet>", "</IndexedLineSet>", scene, flags=re.IGNORECASE)

    # Draw the cage with depth-testing off so it stays visible *through* the
    # other gamut's surface — otherwise a wireframe nested inside the larger
    # gamut would be hidden by it. (This x3dom build supports DepthMode.) Scope
    # it to just the gamut shapes (those now holding an IndexedLineSet), not the
    # axes/labels, so only the cage floats on top.
    def _depth_off(shape: "re.Match") -> str:
        block = shape.group(0)
        if re.search(r"<IndexedLineSet\b", block, re.IGNORECASE):
            block = re.sub(r"(<Appearance\b[^>]*>)",
                           r'\1<DepthMode enableDepthTest="false"></DepthMode>',
                           block, count=1, flags=re.IGNORECASE)
        return block

    scene = re.sub(r"<Shape\b.*?</Shape>", _depth_off, scene,
                   flags=re.IGNORECASE | re.DOTALL)
    return scene


def _with_depth_modes(scene: str) -> str:
    """Give every <Appearance> that has none a <DepthMode readOnly="false">,
    the renderer's own default, so the opacity sliders can switch depth
    writing off by changing an ATTRIBUTE (N1). This x3dom never notices an
    element added later: it listens for DOMNodeInserted, which Chromium no
    longer fires. Appearances that already carry one (the wireframe cage's
    enableDepthTest="false") keep theirs."""
    def add(m: "re.Match") -> str:
        block = m.group(0)
        if re.search(r"<DepthMode\b", block, re.IGNORECASE):
            return block
        return re.sub(r"(<Appearance\b[^>]*?)(/?)>",
                      lambda a: (a.group(1) + '><DepthMode readOnly="false"></DepthMode></Appearance>'
                                 if a.group(2) else
                                 a.group(1) + '><DepthMode readOnly="false"></DepthMode>'),
                      block, count=1, flags=re.IGNORECASE)
    return re.sub(r"<Appearance\b[^>]*?/>|<Appearance\b.*?</Appearance>", add, scene,
                  flags=re.IGNORECASE | re.DOTALL)


def _build_compare_overlay_html(
    primary_html: Path,
    compare_html: Path,
    output_path: Path,
    primary_wire: bool = False,
    compare_wire: bool = False,
) -> bool:
    """Merge compare gamut scene into primary's colorful HTML as a transparent overlay.

    Profile A keeps its natural per-vertex colors and is fully opaque until
    its own sliders move it (K3: the gamut panel's A row sets
    `_chromiqPrimaryOpacity` / `_chromiqPrimarySat`). Profile B keeps its
    natural colors but is rendered semi-transparent so Profile A remains
    visible beneath it.
    Returns True on success.
    """
    try:
        primary_text = primary_html.read_text(encoding="utf-8")
        compare_text = compare_html.read_text(encoding="utf-8")

        if primary_wire:                       # render the image gamut as a cage
            primary_text = _to_wireframe(primary_text)

        m = re.search(r"<[Ss]cene[^>]*>(.*?)</[Ss]cene>", compare_text, re.DOTALL | re.IGNORECASE)
        if not m:
            return False
        compare_scene = _strip_scene_level_dupes(m.group(1))
        if compare_wire:                       # render the printer gamut as a cage
            compare_scene = _to_wireframe(compare_scene)

        # Add transparency to every Material element in the compare scene.
        # Shapes that omit Material (relying on per-vertex Color alone) are
        # handled at runtime by _COMPARE_TRANSPARENCY_JS.
        compare_scene = re.sub(
            r"<[Mm]aterial\b[^>]*/?>",
            _add_material_transparency,
            compare_scene,
        )

        overlay = f'\n<Group id="chromiq-compare">\n{_with_depth_modes(compare_scene)}\n</Group>\n'
        primary_text = _with_depth_modes(primary_text)
        result = re.sub(r"</[Ss]cene>", overlay + "</Scene>", primary_text, count=1, flags=re.IGNORECASE)
        if result == primary_text:
            return False

        result = result.replace("</head>", f"<script>\n{_COMPARE_CONTROLS_JS}</script>\n</head>", 1)

        output_path.write_text(result, encoding="utf-8")
        return True
    except OSError:
        return False


def _patch_html(html_path: Path, themed: bool = True, bg: str = "#111111") -> None:
    """Inject page background, expand X3D canvas, and optionally apply theme colors."""
    try:
        text = html_path.read_text(encoding="utf-8")
        style = (
            "<style>\n"
            f"  html, body {{ background: {bg}; margin: 0; padding: 0;"
            " overflow: hidden; }\n"
            "</style>\n"
        )
        # JS always runs — applyBackground needs the X3D <Background> set
        # in both themed and untinted modes. Colour remap is themed-only
        # and applied in Python below, before write.
        inject = style + "<script>\n" + _THEMED_JS + "</script>\n"
        text = text.replace("</head>", inject + "</head>", 1)
        text = text.replace("height: 70%;", "height: 100vh;", 1)
        text = text.replace("height='70%'", "height='100vh'", 1)
        if themed:
            text = _apply_chromiq_colors(text)
        html_path.write_text(text, encoding="utf-8")
    except OSError:
        pass


@dataclass
class ViewgamResult:
    html_path: str = ""
    intersection_volume: float | None = None
    primary_coverage_pct: float | None = None   # % of primary gamut covered by compare
    compare_coverage_pct: float | None = None   # % of compare gamut covered by primary


class ViewgamRunner(QObject):
    """Wraps viewgam to produce combined X3DOM visualization + coverage statistics."""

    finished = pyqtSignal(object)   # ViewgamResult
    error    = pyqtSignal(str)

    def __init__(self, runner: "ArgyllRunner", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner    = runner
        self._log_lines: list[str] = []
        self._matched_errors: list[tuple[str, str]] = []
        self._matched_warnings: list[tuple[str, str]] = []

    def run(
        self,
        primary_gam:  Path,
        compare_gam:  Path,
        on_line:      Callable[[str], None],
        on_finish:    Callable[[int], None],
        themed:       bool = True,
        primary_html: Path | None = None,
        compare_html: Path | None = None,
        bg:           str  = "#111111",
    ) -> None:
        if self._runner.is_running:
            self.error.emit(tr("Another process is already running."))
            return

        self._log_lines   = []
        self._matched_errors = []
        self._matched_warnings = []
        self._themed      = themed
        self._bg          = bg
        self._primary_html = primary_html
        self._compare_html = compare_html
        work_dir    = Path(tempfile.mkdtemp(prefix="chromiq_viewgam_"))
        output_base = str(work_dir / "combined")

        args = [
            "-i",
            "-c", "r", str(primary_gam),
            "-c", "w", str(compare_gam),
            output_base,
        ]
        log.info("viewgam: %s  [cwd=%s]", " ".join(args), work_dir)

        def _accumulate(line: str) -> None:
            self._log_lines.append(line)
            self._scan_line(line)
            on_line(line)

        def _done(code: int) -> None:
            self._on_done(code, work_dir, on_finish)

        self._runner.run("viewgam", args, work_dir, on_line=_accumulate, on_finish=_done)

    def _scan_line(self, line: str) -> None:
        for pattern, key, fmt in _VIEWGAM_ERROR_PATTERNS:
            m = pattern.search(line)
            if m:
                self._matched_errors.append((key, fmt.format(*m.groups())))
        for pattern, key, fmt in _VIEWGAM_WARNING_PATTERNS:
            m = pattern.search(line)
            if m:
                self._matched_warnings.append((key, fmt.format(*m.groups())))

    def primary_failure(self) -> tuple[str, str] | None:
        return self._matched_errors[0] if self._matched_errors else None

    def captured_warnings(self) -> list[tuple[str, str]]:
        return list(self._matched_warnings)

    def _on_done(
        self,
        code: int,
        work_dir: Path,
        on_finish: Callable[[int], None],
    ) -> None:
        full_log = "\n".join(self._log_lines)
        result   = ViewgamResult()

        m_int = _INTERSECT_RE.search(full_log)
        if m_int:
            result.intersection_volume = float(m_int.group(1))

        coverages = _COVERAGE_RE.findall(full_log)
        if len(coverages) >= 2:
            result.primary_coverage_pct = float(coverages[0][1])
            result.compare_coverage_pct = float(coverages[1][1])

        # Prefer custom overlay HTML (Profile A keeps its natural colours) over
        # viewgam's flat-colour output.
        custom_html = work_dir / "custom_combined.x3d.html"
        if self._primary_html and self._compare_html and _build_compare_overlay_html(
            self._primary_html, self._compare_html, custom_html
        ):
            result.html_path = str(custom_html)
        else:
            viewgam_html = work_dir / "combined.x3d.html"
            if viewgam_html.exists():
                result.html_path = str(viewgam_html)
                _patch_html(viewgam_html, self._themed, self._bg)

        if result.html_path or result.intersection_volume is not None:
            log.info(
                "viewgam: intersect=%.0f cc, A→B=%.1f%%, B→A=%.1f%%",
                result.intersection_volume or 0,
                result.primary_coverage_pct or 0,
                result.compare_coverage_pct or 0,
            )
            self.finished.emit(result)
        elif code != 0:
            failure = self.primary_failure()
            if failure is not None:
                self.error.emit(failure[1])
            else:
                self.error.emit(tr("viewgam exited with code {code}.").format(code=code))
        else:
            self.error.emit(tr("viewgam produced no usable output."))

        on_finish(code)
