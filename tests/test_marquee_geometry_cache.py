"""The marquee caches its cell geometry between paints (it is the whole reason a
988-patch chart can be dragged at all). A cache is only safe if it is thrown away
whenever either of its two inputs changes, so these tests change each input and
insist the drawn geometry moves.

They are written against what is DRAWN, not against the cache attribute, so a
different caching scheme still has to pass them.
"""
import numpy as np
import pytest
from PyQt6.QtGui import QImage, QColor

from ui.scan_grid_marquee import GridSpec, ScanGridMarquee

CHT_A = "/Applications/Argyll/ref/SpyderChecker24.cht"
CHT_B = "/Applications/Argyll/ref/ColorChecker.cht"
CHT_C = "/Applications/Argyll/ref/it8Wolf.cht"


def _marquee(qapp, cht, frac=0.60):
    m = ScanGridMarquee()
    m.resize(500, 400)
    img = QImage(800, 600, QImage.Format.Format_RGB32)
    img.fill(QColor("#808080"))
    m.set_image(img)
    m.set_grid(GridSpec.from_cht(open(cht, encoding="utf-8").read()))
    m.set_sample_fraction(frac)
    m.reset_selection_grid()
    return m


def _drawn(m):
    from ui.scan_grid_marquee import unit_quad_homography
    xs, ys, stride = m._map_cells(unit_quad_homography(m._corners))
    return np.column_stack([xs, ys]), stride


def test_a_new_sample_fraction_moves_the_sample_box(qapp):
    m = _marquee(qapp, CHT_A, 0.60)
    before, stride = _drawn(m)
    m.set_sample_fraction(0.30)
    after, _ = _drawn(m)
    assert before.shape == after.shape
    # the patch cell itself must NOT move …
    cell = slice(0, stride - 4)
    assert np.allclose(before.reshape(-1, stride, 2)[:, cell],
                       after.reshape(-1, stride, 2)[:, cell])
    # … and the sample box must shrink towards it
    smp = slice(stride - 4, stride)
    assert not np.allclose(before.reshape(-1, stride, 2)[:, smp],
                           after.reshape(-1, stride, 2)[:, smp]), \
        "the sample area changed and the drawn box did not — stale cache"


def test_a_new_chart_replaces_the_geometry(qapp):
    """Deliberately a 24-patch chart followed by a 288-patch one: two charts of
    the SAME patch count would let a stale cache pass, because `set_grid` also
    re-seeds the quad and that moves every point on its own."""
    m = _marquee(qapp, CHT_A)                     # SpyderChecker24 — 24 patches
    a, _ = _drawn(m)
    assert len(a) == 24 * 8
    m.set_grid(GridSpec.from_cht(open(CHT_C, encoding="utf-8").read()))   # it8Wolf — 288
    b, _ = _drawn(m)
    assert len(b) == 288 * 8, \
        "the chart changed and the drawn mesh did not — stale cache"


def test_moving_the_quad_does_not_rebuild_but_does_move(qapp):
    m = _marquee(qapp, CHT_A)
    a, _ = _drawn(m)
    key = id(m._cell_uv_cache)
    m.set_corners([(10, 20), (700, 30), (690, 500), (20, 490)])
    b, _ = _drawn(m)
    assert not np.allclose(a, b), "the quad moved and the mesh did not"
    assert id(m._cell_uv_cache) == key, \
        "moving the quad rebuilt the cell geometry — that is the cost this cache exists to remove"


def test_the_vectorised_transform_is_the_scalar_one(qapp):
    """`_map_cells` must be bit-identical to the per-point `apply_h` +
    `_to_widget` pair it replaced — not merely close."""
    from ui.scan_grid_marquee import apply_h, unit_quad_homography
    for cht in (CHT_A, CHT_B, "/Applications/Argyll/ref/it8Wolf.cht"):
        m = _marquee(qapp, cht)
        for quad in ([(10, 20), (700, 30), (690, 500), (20, 490)],
                     [(300.5, 250.25), (620, 262), (615, 470), (295, 458)]):
            m.set_corners(quad)
            h = unit_quad_homography(m._corners)
            xs, ys, stride = m._map_cells(h)
            u, v, _ = m._cell_uv()
            for i in range(0, len(u), max(1, len(u) // 37)):
                w = m._to_widget(*apply_h(h, u[i], v[i]))
                assert w.x() == xs[i] and w.y() == ys[i], (cht, i, w.x(), xs[i])


def _render(m):
    from PyQt6.QtGui import QImage, QPainter
    surf = QImage(m.width(), m.height(), QImage.Format.Format_ARGB32_Premultiplied)
    surf.fill(0)
    p = QPainter(surf)
    try:
        m.render(p)
    finally:
        p.end()
    import numpy as _np
    b = surf.constBits(); b.setsize(surf.sizeInBytes())
    return _np.frombuffer(b, dtype=_np.uint8).reshape(surf.height(), -1, 4).copy()


def _in_mode(monkeypatch, mode):
    monkeypatch.setattr(ScanGridMarquee, "_appearance", lambda self: mode)


def test_only_the_under_stroke_is_aliased_while_the_button_is_down(qapp, monkeypatch):
    """The drag-time speed-up must not leak into the picture the user judges.

    Only the UNDER-STROKE loses antialiasing, and only while moving. It is a
    3.0-3.4 px stroke, where antialiasing costs 5.7x; the accent that the eye
    actually aims with is 1.0-1.4 px, where it costs 1.5x and is kept. Measured
    on 988 patches in Neutral: 48.7 ms both smooth, 25.2 ms this way."""
    _in_mode(monkeypatch, "neutral")              # the only appearance with one
    m = _marquee(qapp, CHT_C)
    at_rest = _render(m)
    m._drag = 0                                   # exactly what mousePressEvent sets
    moving = _render(m)
    m._drag = -1
    after = _render(m)
    assert not np.array_equal(at_rest, moving), \
        "the drag draws the same thing as the rest state — the speed-up is not happening"
    assert np.array_equal(at_rest, after), \
        "the mesh did not go back to what it was when the drag ended"
    assert len(np.unique(at_rest.reshape(-1, 4), axis=0)) > \
        len(np.unique(moving.reshape(-1, 4), axis=0)), \
        "the moving frame is not the aliased one"


def test_an_appearance_with_no_under_stroke_draws_a_drag_exactly_as_it_rests(
        qapp, monkeypatch):
    """Light and Dark have no under-stroke, so there is nothing wide to alias
    and a drag must be pixel-for-pixel the resting frame. This is what pins that
    the ACCENT is never aliased: if the speed-up ever widens to that pass, this
    is the test that goes red."""
    for mode in ("light", "dark"):
        _in_mode(monkeypatch, mode)
        m = _marquee(qapp, CHT_C)
        at_rest = _render(m)
        m._drag = 0
        moving = _render(m)
        assert np.array_equal(at_rest, moving), (
            f"{mode}: the drag changed the picture, but this appearance has no "
            f"under-stroke — the accent must never be drawn aliased")


def test_releasing_the_mouse_repaints(qapp):
    """Without this the aliased frame would stay on screen after the drag."""
    import inspect
    src = inspect.getsource(ScanGridMarquee.mouseReleaseEvent)
    assert "self.update()" in src, \
        "mouseReleaseEvent does not repaint — the aliased mesh would stay up"
