"""N1 (Knut, testing 4.3.8-beta.3): with profile A LARGER than B, lowering A's
opacity showed "only a small part of B on the surface of A, nothing inside";
B appeared only once A was under about 10 %.

Measured on screen with Knut's run 1 (matte, A) and run 3 (plain, B), reading
back what x3dom's RENDERER held for each gamut surface:

* the page script switched depth writing off by CREATING a <DepthMode> element.
  This x3dom (1.6.3) learns of a new element only from the DOMNodeInserted
  event, which Chromium no longer fires, so the node never reached the
  renderer (``depthMode_attached: false``): A kept writing depth and hid
  everything behind its front surface. Below 10 % its fragments fall under
  x3dom's alpha clip and are discarded, which is why B then appeared.
* x3dom sorts a shape into its opaque or transparent pass once, from the
  transparency it had when loaded, so A (loaded opaque) stayed in the opaque
  pass however translucent it became.
* the page script waited for an 'x3dom-initialized' event this x3dom never
  fires, and the panel's page-load push could arrive before x3dom had built
  its nodes and be lost: after a second analysis B was drawn at 50 % under a
  slider that said 100 %.

The fix builds the page with a <DepthMode> in every Appearance, changes only
attributes (which x3dom does see), sets sortType explicitly, and applies the
slider values once x3dom holds the scene. These tests fail on the old code.
"""
from __future__ import annotations

import re
from pathlib import Path


_SCENE = ("<html><head></head><body><X3D><Scene>"
          "<Shape><Appearance><Material diffuseColor='1 1 1'></Material></Appearance>"
          "<Box size='1 1 1'></Box></Shape>"
          "<Shape><IndexedFaceSet coordIndex='0 1 2 -1' solid='true'>"
          "<Coordinate point='0 0 0 1 0 0 0 1 0'/><Color color='1 0 0 0 1 0 0 0 1'/>"
          "</IndexedFaceSet><Appearance><Material shininess='0.95'></Material>"
          "</Appearance></Shape></Scene></X3D></body></html>")


def _combined(tmp_path: Path, **kw) -> str:
    from workflow.viewgam_runner import _build_compare_overlay_html
    p = tmp_path / "a.html"; p.write_text(_SCENE, encoding="utf-8")
    c = tmp_path / "b.html"; c.write_text(_SCENE, encoding="utf-8")
    out = tmp_path / "combined.html"
    assert _build_compare_overlay_html(p, c, out, **kw)
    return out.read_text(encoding="utf-8")


def _scene_part(html: str) -> str:
    return re.search(r"<Scene>(.*)</Scene>", html, re.S | re.I).group(1)


def _page_script() -> str:
    from workflow.viewgam_runner import _COMPARE_CONTROLS_JS
    return _COMPARE_CONTROLS_JS


def test_every_appearance_of_both_gamuts_is_built_with_a_depth_mode(tmp_path):
    scene = _scene_part(_combined(tmp_path))
    apps = re.findall(r"<Appearance\b.*?</Appearance>", scene, re.S | re.I)
    assert len(apps) == 4, apps                       # 2 shapes x A and B
    for a in apps:
        assert len(re.findall(r"<DepthMode\b", a, re.I)) == 1, a
    b_part = scene[scene.index('id="chromiq-compare"'):]
    assert re.search(r"<DepthMode readOnly=\"false\">", b_part)


def test_the_depth_mode_starts_as_the_renderer_s_own_default(tmp_path):
    # readOnly="false" with depth testing on is exactly what x3dom does with no
    # DepthMode at all, so an untouched page draws as it always did.
    scene = _scene_part(_combined(tmp_path))
    dms = re.findall(r"<DepthMode\b[^>]*>", scene, re.I)
    assert len(dms) == 4
    for dm in dms:
        assert 'readOnly="false"' in dm and "enableDepthTest" not in dm


def test_a_wireframe_cage_keeps_its_own_depth_mode_only(tmp_path):
    scene = _scene_part(_combined(tmp_path, primary_wire=True))
    cage = scene[:scene.index('id="chromiq-compare"')]
    shape = re.findall(r"<Shape\b.*?</Shape>", cage, re.S | re.I)[1]
    assert shape.count("<DepthMode") == 1
    assert 'enableDepthTest="false"' in shape


def test_the_page_script_never_adds_a_depth_mode_element():
    js = _page_script()
    assert "createElement('depthmode')" not in js
    assert 'createElement("depthmode")' not in js


def test_a_translucent_gamut_is_sorted_into_the_transparent_pass():
    js = _page_script()
    body = js[js.index("function setDepth"):js.index("function applyTransparency")]
    assert "setAttribute('readOnly'" in body
    assert "setAttribute('sortType', transparent ? 'transparent' : 'opaque')" in body


def test_the_values_are_applied_once_x3dom_holds_the_scene():
    js = _page_script()
    assert "_x3domNode" in js and "window._chromiqWhenReady" in js
    assert "addEventListener('DOMContentLoaded'" in js


def test_a_reloaded_page_gets_the_sliders_once_x3dom_is_ready(qtbot):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.gamut_panel import GamutPanel
    st = AppSettings()
    panel = GamutPanel(ArgyllRunner(st), st, None)
    qtbot.addWidget(panel)

    class _Page:
        def __init__(self):
            self.js = []

        def runJavaScript(self, js, *a):
            self.js.append(js)

    class _View:
        def __init__(self):
            self.p = _Page()

        def page(self):
            return self.p

    view = _View()
    panel._web_view = view
    panel._view_combined_btn.setChecked(True)
    panel._opacity_slider.setValue(100)
    panel._a_opacity_slider.setValue(35)
    view.p.js.clear()
    panel._on_page_loaded(True)
    push = [j for j in view.p.js if "_chromiqCompareOpacity" in j]
    assert push, view.p.js
    js = push[-1]
    assert "window._chromiqCompareOpacity=0.00" in js
    assert "window._chromiqPrimaryOpacity=0.65" in js
    assert "_chromiqWhenReady" in js
    # both applied inside the ready callback, not before it
    ready = js.index("_chromiqWhenReady")
    assert js.index("_chromiqApplyCompare()") > ready
    assert js.index("_chromiqApplyPrimary()") > ready
    panel._web_view = None
