"""3D RGB-cube visualisation of a chart's patch set (Tools → layout editor).

Turns the editor's flat list of 0..100 RGB device tuples into a self-contained
Plotly ``Scatter3d`` page: every patch is a dot placed at its own (R, G, B)
coordinate and painted in its own colour, inside a 0..100 wireframe cube with a
neutral (black→white) axis drawn through it. Rotating / zooming the cube makes
gamut coverage and patch-density clumping obvious at a glance — the thing the
swatch grid and 2D page preview can't show.

Qt-free and unit-testable: the popup in :mod:`ui.dialogs.ti2_relayout_dialog`
just writes the returned HTML to a temp file and loads it in a QWebEngineView.
The heavy ``plotly-gl3d.min.js`` bundle is referenced by ``file://`` URL (not
inlined) so the page stays small enough for any loader and ships from
``assets/`` with the rest of the app.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np


@dataclass
class CubeStats:
    """Coverage / density summary shown alongside the 3D cube."""
    count: int
    nn_mean: float          # mean nearest-neighbour RGB distance (0..100 scale)
    nn_min: float           # closest pair distance — small ⇒ near-duplicates
    occupancy_pct: float    # % of a 10×10×10 cube grid that holds ≥1 patch

    def summary(self) -> str:
        from core.i18n import tr
        if self.count == 0:
            return tr("No patches to analyse.")
        return tr("{count} patches · gamut fill {fill:.0f}% "
                  "· spacing mean {mean:.1f}, closest {closest:.1f} "
                  "(0–100 RGB)").format(count=self.count,
                                        fill=self.occupancy_pct,
                                        mean=self.nn_mean,
                                        closest=self.nn_min)


def _as_array(program: list[tuple[float, ...]]) -> np.ndarray:
    """Coerce the program to an ``[N, 3]`` float array of 0..100 RGB."""
    if not program:
        return np.zeros((0, 3), dtype=float)
    arr = np.asarray([p[:3] for p in program], dtype=float)
    return arr.reshape(-1, 3)


def cube_stats(program: list[tuple[float, ...]]) -> CubeStats:
    """Coverage / density metrics for a patch program.

    * ``occupancy_pct`` — patches binned into a 10×10×10 grid over the 0..100
      cube; the fraction of occupied cells is a cheap, monotone proxy for "how
      much of the colour space is sampled" that doesn't need a convex hull.
    * ``nn_mean`` / ``nn_min`` — nearest-neighbour RGB distances, computed in
      blocks so a few-thousand-patch chart stays within a sane memory budget.
      A tiny ``nn_min`` flags near-duplicate patches; a large ``nn_mean`` with
      low occupancy flags sparse, uneven coverage.
    """
    arr = _as_array(program)
    n = len(arr)
    if n == 0:
        return CubeStats(0, 0.0, 0.0, 0.0)

    # Occupancy over a 10×10×10 grid (clamp to keep 100.0 in the last cell).
    cells = np.clip((arr / 10.0).astype(int), 0, 9)
    keys = cells[:, 0] * 100 + cells[:, 1] * 10 + cells[:, 2]
    occupancy = len(np.unique(keys)) / 1000.0 * 100.0

    if n == 1:
        return CubeStats(1, 0.0, 0.0, occupancy)

    # Block-wise nearest-neighbour distances (avoid an N×N matrix all at once).
    nn = np.empty(n, dtype=float)
    block = 256
    for i in range(0, n, block):
        chunk = arr[i:i + block]                                  # [b, 3]
        d = np.linalg.norm(chunk[:, None, :] - arr[None, :, :], axis=2)  # [b, N]
        # Mask each point's distance to itself.
        for j in range(len(chunk)):
            d[j, i + j] = np.inf
        nn[i:i + block] = d.min(axis=1)
    return CubeStats(n, float(nn.mean()), float(nn.min()), occupancy)


# 8 corners of the 0..100 cube, then the 12 edges as corner-index pairs.
_CUBE_CORNERS = [(x, y, z) for x in (0, 100) for y in (0, 100) for z in (0, 100)]
_CUBE_EDGES = [
    (a, b) for a in range(8) for b in range(a + 1, 8)
    # an edge connects corners differing in exactly one axis
    if sum(_CUBE_CORNERS[a][k] != _CUBE_CORNERS[b][k] for k in range(3)) == 1
]


def _edge_lines() -> tuple[list, list, list]:
    """Build x/y/z arrays tracing all 12 cube edges, ``None``-separated so a
    single Plotly line trace draws the whole wireframe."""
    xs: list = []
    ys: list = []
    zs: list = []
    for a, b in _CUBE_EDGES:
        ca, cb = _CUBE_CORNERS[a], _CUBE_CORNERS[b]
        xs += [ca[0], cb[0], None]
        ys += [ca[1], cb[1], None]
        zs += [ca[2], cb[2], None]
    return xs, ys, zs


def _points_trace(arr: np.ndarray, *, name: str, size: float, opacity: float,
                  hover_prefix: str, numbered: bool = False) -> dict:
    """A ``scatter3d`` marker trace placing each patch at its (R,G,B) and
    painting it its own colour. ``size`` / ``opacity`` let the caller dim the
    already-present patches so the freshly-generated ones read on top.
    ``numbered`` puts each patch's 1-based number in the hover label (the layout
    editor's 3D view, to locate a patch in the swatch/preview — #67)."""
    rgb255 = np.clip(np.round(arr / 100.0 * 255.0), 0, 255).astype(int)
    colors = [f"rgb({r},{g},{b})" for r, g, b in rgb255.tolist()]
    if numbered:
        hover = [f"patch #: {i + 1} · RGB {r} {g} {b}"
                 for i, (r, g, b) in enumerate(rgb255.tolist())]
    else:
        hover = [f"{hover_prefix} · RGB {r} {g} {b}" for r, g, b in rgb255.tolist()]
    return {
        "type": "scatter3d", "mode": "markers", "name": name,
        "x": arr[:, 0].tolist(), "y": arr[:, 1].tolist(),
        "z": arr[:, 2].tolist(),
        "marker": {"size": size, "color": colors,
                   "line": {"width": 0}, "opacity": opacity},
        "text": hover, "hoverinfo": "text", "showlegend": False,
    }


def cube_traces(
    new_program: list[tuple[float, ...]],
    existing_program: list[tuple[float, ...]] | None = None,
    *,
    fg: str = "#cccccc",
    grid: str = "#444444",
    numbered: bool = False,
) -> list[dict]:
    """The Plotly ``data`` list: wireframe + neutral axis + patch markers.

    When ``existing_program`` is given (the editor's Add flow), its patches are
    drawn smaller and semi-transparent as a separate trace and the freshly
    generated ``new_program`` patches are drawn full-size on top — one merged
    cloud in which the about-to-be-added patches still stand out.
    """
    ex_arr = _as_array(existing_program or [])
    new_arr = _as_array(new_program)
    ex, ey, ez = _edge_lines()
    cube = {
        "type": "scatter3d", "mode": "lines", "name": "cube",
        "x": ex, "y": ey, "z": ez,
        "line": {"color": grid, "width": 2}, "hoverinfo": "skip",
        "showlegend": False,
    }
    neutral = {
        "type": "scatter3d", "mode": "lines", "name": "neutral axis",
        "x": [0, 100], "y": [0, 100], "z": [0, 100],
        "line": {"color": fg, "width": 2, "dash": "dot"}, "hoverinfo": "skip",
        "showlegend": False,
    }
    data = [cube, neutral]
    has_existing = len(ex_arr) > 0
    if has_existing:
        data.append(_points_trace(ex_arr, name="existing", size=2.4,
                                  opacity=0.35, hover_prefix="existing"))
    data.append(_points_trace(
        new_arr, name="new" if has_existing else "patches",
        size=3.6, opacity=1.0,
        hover_prefix="new" if has_existing else "patch", numbered=numbered))
    return data


def combined_summary(
    new_program: list[tuple[float, ...]],
    existing_program: list[tuple[float, ...]] | None = None,
) -> str:
    """Footer text — a plain coverage line, or an ``N existing + M new`` split
    over the combined set when there are already-present patches."""
    existing = list(existing_program or [])
    if not existing:
        return cube_stats(new_program).summary()
    from core.i18n import tr
    combined = cube_stats(existing + list(new_program))
    return tr("{ex} existing + {new} new · gamut fill {fill:.0f}% "
              "(combined)").format(ex=len(existing), new=len(new_program),
                                   fill=combined.occupancy_pct)


def cube_payload(
    new_program: list[tuple[float, ...]],
    existing_program: list[tuple[float, ...]] | None = None,
    *,
    fg: str = "#cccccc",
    grid: str = "#444444",
) -> dict:
    """JSON-serialisable ``{"data", "stats"}`` for a live in-place update.

    The live preview window feeds this (via ``json.dumps``) to the page's
    ``cqUpdateCube`` function, which calls ``Plotly.react`` — no page reload,
    so the cube redraws smoothly while generator settings change."""
    return {
        "data": cube_traces(new_program, existing_program, fg=fg, grid=grid),
        "stats": combined_summary(new_program, existing_program),
    }


def _lab_layout(bg: str, fg: str, grid: str) -> dict:
    """Plotly layout for the Lab-space scatter (#72 state 3): a*/b* on the
    floor, L* vertical — the standard way a gamut cloud is shown."""
    def _axis(title: str, rng: list) -> dict:
        return {"title": title, "range": rng, "color": fg,
                "gridcolor": grid, "zerolinecolor": grid,
                "backgroundcolor": bg, "showbackground": True}
    return {
        "paper_bgcolor": bg, "plot_bgcolor": bg,
        "margin": {"l": 0, "r": 0, "t": 0, "b": 0},
        "showlegend": False,
        "scene": {
            "xaxis": _axis("a*", [-110, 110]),
            "yaxis": _axis("b*", [-110, 110]),
            "zaxis": _axis("L*", [0, 100]),
            "aspectmode": "cube",
            "camera": {"eye": {"x": 1.5, "y": 1.5, "z": 1.3}},
        },
    }


#: Samples along each of the cube's 12 edges, and per side of each face, when
#: the device cube is mapped into L*a*b* to outline a profile's gamut.
OUTLINE_EDGE_STEPS = 33
#: The SAME as the edges' (Knut, #182 6144104040: "Why do the dark grey line
#: not align with the outer edges of the lighter grey gamut shell?"). With 17
#: the skin's border was a chord across every second point of the line beside
#: it, up to 4.2 ΔE*ab off it where his CLJ5550's lines hook round near a
#: corner; at 33 the skin's border passes through every point of the line.
OUTLINE_FACE_STEPS = OUTLINE_EDGE_STEPS


@dataclass
class GamutOutline:
    """A profile's gamut as the device cube mapped into L*a*b*.

    Every colour a printer can print is the image of some ink amount, so the
    gamut's surface is the image of the device cube's six faces and its ridges
    are the images of the cube's twelve edges (the idea the ChromIQ Gamut
    Viewer uses to draw a profile's gamut, ``gamutview._device_cube_surface``).
    ``edges``: twelve polylines of Lab points; ``vertices``/``faces``: a
    triangle mesh of the six sides."""
    edges: list
    vertices: list
    faces: list


def _outline_device_rows(edge_steps: int, face_steps: int):
    """The device values to read: the 12 edges, then the 6 faces' grids."""
    t = np.linspace(0.0, 100.0, edge_steps)
    edges = []
    for a, b in _CUBE_EDGES:
        ca, cb = np.asarray(_CUBE_CORNERS[a], float), np.asarray(_CUBE_CORNERS[b], float)
        edges.append(ca[None, :] + (cb - ca)[None, :] * (t[:, None] / 100.0))
    g = np.linspace(0.0, 100.0, face_steps)
    u, v = np.meshgrid(g, g, indexing="ij")
    faces = []
    for axis in range(3):
        for value in (0.0, 100.0):
            cols = [u.ravel(), v.ravel()]
            cols.insert(axis, np.full(u.size, value))
            faces.append(np.stack(cols, axis=1))
    return edges, faces


def gamut_outline(profile, bin_dir, *, intent: str = "a",
                  runner=None) -> "GamutOutline":
    """The outline of *profile*'s gamut in L*a*b* (one xicclu call, in
    *intent*). Raises what :func:`workflow.xicclu_runner.forward_lab` raises."""
    import subprocess
    from workflow.xicclu_runner import forward_lab
    edges, faces = _outline_device_rows(OUTLINE_EDGE_STEPS, OUTLINE_FACE_STEPS)
    rows = np.vstack(edges + faces)
    lab = np.asarray(forward_lab([tuple(r) for r in rows], profile, bin_dir,
                                 intent=intent,
                                 runner=runner or subprocess.run), dtype=float)
    if lab.shape != (len(rows), 3):
        raise ValueError("the profile did not answer for every outline point")
    ne = OUTLINE_EDGE_STEPS
    out_edges = [lab[i * ne:(i + 1) * ne].tolist() for i in range(len(edges))]
    base = len(edges) * ne
    n = OUTLINE_FACE_STEPS
    verts: list = []
    tris: list = []
    for f in range(len(faces)):
        off = base + f * n * n
        start = len(verts)
        verts.extend(lab[off:off + n * n].tolist())
        for i in range(n - 1):
            for j in range(n - 1):
                p = start + i * n + j
                tris.append((p, p + 1, p + n))
                tris.append((p + 1, p + n + 1, p + n))
    return GamutOutline(out_edges, verts, tris)


#: How see-through the gamut's skin is drawn (0 invisible, 1 solid).
SKIN_OPACITY = 0.14

#: How see-through the twelve lines (the seams on the skin) are drawn.
LINE_OPACITY = 0.45


def outline_traces(outline: "GamutOutline", *, fg: str = "#cccccc") -> list:
    """Plotly traces for :class:`GamutOutline`: the twelve ridges as lines and
    the six sides as a faint see-through skin, neither hoverable."""
    xs: list = []
    ys: list = []
    zs: list = []
    for line in outline.edges:
        for L, a, b in line:
            xs.append(a)
            ys.append(b)
            zs.append(L)
        xs.append(None)
        ys.append(None)
        zs.append(None)
    ridges = {"type": "scatter3d", "mode": "lines", "name": "gamut edges",
              "x": xs, "y": ys, "z": zs,
              "line": {"color": fg, "width": 2}, "opacity": LINE_OPACITY,
              "hoverinfo": "skip", "showlegend": False}
    if not outline.vertices or not outline.faces:
        return [ridges]
    v = np.asarray(outline.vertices, dtype=float)
    f = np.asarray(outline.faces, dtype=int)
    skin = {"type": "mesh3d", "name": "gamut",
            "x": v[:, 1].tolist(), "y": v[:, 2].tolist(), "z": v[:, 0].tolist(),
            "i": f[:, 0].tolist(), "j": f[:, 1].tolist(), "k": f[:, 2].tolist(),
            "color": fg, "opacity": SKIN_OPACITY, "flatshading": False,
            # Lit, so the skin reads as a curved surface with its own
            # outline: the twelve lines are seams ON it (two inks at 0 or
            # 100), and between them a printer's skin can bulge well past
            # them (his CLJ5550: up to 39 ΔE*ab, dark violet; its most
            # colourful green is at G=53, not on any seam). A flat, faint
            # skin hid where it turns away, so the seams looked like its
            # edges and did not match them.
            "lighting": {"ambient": 0.55, "diffuse": 0.6, "specular": 0.05,
                         "roughness": 0.9, "fresnel": 0.4},
            "lightposition": {"x": 1000, "y": 2000, "z": 3000},
            "hoverinfo": "skip", "showlegend": False}
    return [skin, ridges]


def lab_spacing_summary(labs: list[tuple[float, float, float]]) -> str:
    """The footer for the colour view: how many patches and how far apart, as
    colour differences (ΔE*ab), the way the cube's footer reports RGB."""
    from core.i18n import decimal_text, tr
    arr = np.asarray(labs, dtype=float).reshape(-1, 3)
    if len(arr) < 2:
        return tr("No patches to analyse.")
    d = np.sqrt(((arr[:, None, :] - arr[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    nn = d.min(axis=1)
    return tr("{n} patches as colours, through the profile · spacing median "
              "{median}, closest {closest} (ΔE*ab)").format(
                  n=len(arr), median=decimal_text(float(np.median(nn)), 2),
                  closest=decimal_text(float(nn.min()), 2))


def lab_payload(
    labs: list[tuple[float, float, float]],
    colors_rgb255: list[tuple[int, int, int]],
    *,
    bg: str = "#111111",
    fg: str = "#cccccc",
    grid: str = "#444444",
    outline: "GamutOutline | None" = None,
    stats: "str | None" = None,
) -> dict:
    """``{"data", "stats", "layout"}`` for the state-3 Lab scatter (#72).

    Each multi-ink patch is plotted at its **measured-model position** —
    the Lab the preconditioning profile predicts (``xicclu -ff``) — painted
    in its display-approximation colour. The dotted neutral axis (a=b=0)
    anchors the eye the same way the RGB cube's diagonal does.
    """
    neutral = {
        "type": "scatter3d", "mode": "lines", "name": "neutral axis",
        "x": [0, 0], "y": [0, 0], "z": [0, 100],
        "line": {"color": fg, "width": 2, "dash": "dot"}, "hoverinfo": "skip",
        "showlegend": False,
    }
    colors = [f"rgb({r},{g},{b})" for r, g, b in colors_rgb255]
    hover = [f"L {L:.1f} · a {a:.1f} · b {b:.1f}" for L, a, b in labs]
    points = {
        "type": "scatter3d", "mode": "markers", "name": "patches",
        "x": [a for _L, a, _b in labs],
        "y": [b for _L, _a, b in labs],
        "z": [L for L, _a, _b in labs],
        "marker": {"size": 3.6, "color": colors,
                   "line": {"width": 0}, "opacity": 1.0},
        "text": hover, "hoverinfo": "text", "showlegend": False,
    }
    from core.i18n import tr
    if stats is None:
        stats = tr("{n} patches · Lab positions via the preconditioning profile"
                   ).format(n=len(labs))
    data = [neutral]
    layout = _lab_layout(bg, fg, grid)
    if outline is not None:
        data += outline_traces(outline, fg=fg)
        layout = _true_scale_lab_layout(layout, labs, outline)
    data.append(points)
    return {"data": data, "stats": stats, "layout": layout}


def _true_scale_lab_layout(layout: dict, labs, outline: "GamutOutline") -> dict:
    """The colour view drawn TO SCALE: one ΔE*ab is the same length along L*,
    a* and b*, and the box fits the gamut. The fixed ±110 × 0..100 box drawn
    as a cube stretches L* 2.2 times against a* and b*, so patches evenly
    spaced as colours would look squeezed sideways, which is the very thing
    this view exists to show."""
    pts = [p for line in outline.edges for p in line] + list(outline.vertices)
    pts += [tuple(p) for p in labs]
    arr = np.asarray(pts, dtype=float).reshape(-1, 3)
    arr = arr[np.isfinite(arr).all(axis=1)]
    if not len(arr):
        return layout
    lo = arr.min(axis=0) - 5.0
    hi = arr.max(axis=0) + 5.0
    lo[0], hi[0] = max(0.0, lo[0]), min(105.0, hi[0])
    span = hi - lo
    # The longest side a little longer than Plotly's unit cube, so a gamut
    # flatter than a cube still fills the window at the default camera.
    big = (float(span.max()) or 1.0) / 1.4
    scene = dict(layout["scene"])
    scene["xaxis"] = dict(scene["xaxis"], range=[float(lo[1]), float(hi[1])])
    scene["yaxis"] = dict(scene["yaxis"], range=[float(lo[2]), float(hi[2])])
    scene["zaxis"] = dict(scene["zaxis"], range=[float(lo[0]), float(hi[0])])
    scene["aspectmode"] = "manual"
    scene["aspectratio"] = {"x": float(span[1] / big), "y": float(span[2] / big),
                            "z": float(span[0] / big)}
    return dict(layout, scene=scene)


def _controls_hint() -> str:
    """One-line, visible mouse+keyboard help for the 3D cube (#66). Full detail
    lives in the dialog's ⓘ tooltip."""
    from core.i18n import tr
    return tr("Drag to rotate · scroll to zoom · right- or middle-drag to pan · "
              "arrow keys rotate, Shift+arrows pan, +/− zoom")


def _cube_layout(bg: str, fg: str, grid: str) -> dict:
    def _axis(title: str) -> dict:
        return {"title": title, "range": [0, 100], "color": fg,
                "gridcolor": grid, "zerolinecolor": grid,
                "backgroundcolor": bg, "showbackground": True}
    return {
        "paper_bgcolor": bg, "plot_bgcolor": bg,
        "margin": {"l": 0, "r": 0, "t": 0, "b": 0},
        "showlegend": False,
        "scene": {
            "xaxis": _axis("R"), "yaxis": _axis("G"), "zaxis": _axis("B"),
            "aspectmode": "cube",
            "camera": {"eye": {"x": 1.5, "y": 1.5, "z": 1.3}},
        },
    }


# Reusable JS: middle-button (wheel-click) drag → pan a Plotly 3D plot by id
# (#64), and keep two plots' cameras in sync (#66). Emitted into both the
# single and dual cube pages.
_CUBE_JS_HELPERS = """
var cqSub = function(a,b){return {x:a.x-b.x,y:a.y-b.y,z:a.z-b.z};};
var cqAdd = function(a,b){return {x:a.x+b.x,y:a.y+b.y,z:a.z+b.z};};
var cqScl = function(a,s){return {x:a.x*s,y:a.y*s,z:a.z*s};};
var cqCross = function(a,b){return {x:a.y*b.z-a.z*b.y,y:a.z*b.x-a.x*b.z,z:a.x*b.y-a.y*b.x};};
var cqLen = function(a){return Math.hypot(a.x,a.y,a.z)||1;};
var cqNrm = function(a){return cqScl(a,1/cqLen(a));};
// Rodrigues rotation of v around a (normalised) axis by angle ang.
var cqRot = function(v,a,ang){
  var c=Math.cos(ang), s=Math.sin(ang), d=v.x*a.x+v.y*a.y+v.z*a.z, cr=cqCross(a,v);
  return {x:v.x*c+cr.x*s+a.x*d*(1-c), y:v.y*c+cr.y*s+a.y*d*(1-c), z:v.z*c+cr.z*s+a.z*d*(1-c)};
};
var cqCam = function(gd){
  var c=(gd.layout&&gd.layout.scene&&gd.layout.scene.camera)||{eye:{x:1.5,y:1.5,z:1.3}};
  return {eye:c.eye, center:c.center||{x:0,y:0,z:0}, up:c.up||{x:0,y:0,z:1}};
};
function cqInstallPan(plotId) {
  var gd = document.getElementById(plotId);
  var panning = false, lx = 0, ly = 0;
  gd.addEventListener("mousedown", function(e){
    if(e.button===1){panning=true;lx=e.clientX;ly=e.clientY;e.preventDefault();}
  }, true);
  window.addEventListener("mousemove", function(e){
    if(!panning)return;
    var dx=e.clientX-lx, dy=e.clientY-ly; lx=e.clientX; ly=e.clientY;
    var c=cqCam(gd), fwd=cqNrm(cqSub(c.center,c.eye)), right=cqNrm(cqCross(fwd,c.up)), tup=cqNrm(cqCross(right,fwd));
    var rect=gd.getBoundingClientRect(), k=cqLen(cqSub(c.eye,c.center))/Math.max(1,rect.height);
    var t=cqAdd(cqScl(right,-dx*k),cqScl(tup,dy*k));
    Plotly.relayout(gd,{"scene.camera":{eye:cqAdd(c.eye,t),center:cqAdd(c.center,t),up:c.up}});
  }, true);
  window.addEventListener("mouseup", function(e){ if(e.button===1) panning=false; }, true);
}
// Keyboard: arrows rotate, Shift+arrows pan, +/- zoom (operates on the camera
// via the public relayout API, so it stays in sync with the mouse).
function cqInstallKeys(plotId) {
  var gd = document.getElementById(plotId);
  document.addEventListener("keydown", function(e){
    var k=e.key, c=cqCam(gd), v=cqSub(c.eye,c.center);
    var fwd=cqNrm(cqScl(v,-1)), right=cqNrm(cqCross(fwd,c.up)), tup=cqNrm(cqCross(right,fwd));
    var ang=0.12, applied=null;
    if(e.shiftKey && (k==="ArrowLeft"||k==="ArrowRight"||k==="ArrowUp"||k==="ArrowDown")){
      var step=cqLen(v)*0.06, t={x:0,y:0,z:0};
      if(k==="ArrowLeft") t=cqScl(right,-step); else if(k==="ArrowRight") t=cqScl(right,step);
      else if(k==="ArrowUp") t=cqScl(tup,step); else t=cqScl(tup,-step);
      applied={eye:cqAdd(c.eye,t), center:cqAdd(c.center,t), up:c.up};
    } else if(k==="ArrowLeft"){ applied={eye:cqAdd(c.center,cqRot(v,c.up,-ang)), center:c.center, up:c.up}; }
    else if(k==="ArrowRight"){ applied={eye:cqAdd(c.center,cqRot(v,c.up,ang)), center:c.center, up:c.up}; }
    else if(k==="ArrowUp"){ applied={eye:cqAdd(c.center,cqRot(v,right,ang)), center:c.center, up:c.up}; }
    else if(k==="ArrowDown"){ applied={eye:cqAdd(c.center,cqRot(v,right,-ang)), center:c.center, up:c.up}; }
    else if(k==="+"||k==="="){ applied={eye:cqAdd(c.center,cqScl(v,0.9)), center:c.center, up:c.up}; }
    else if(k==="-"||k==="_"){ applied={eye:cqAdd(c.center,cqScl(v,1.1)), center:c.center, up:c.up}; }
    if(!applied) return;
    e.preventDefault();
    Plotly.relayout(gd, {"scene.camera": applied});
  });
}
function cqLinkCameras(idA, idB) {
  // Keep both cubes' cameras locked together CONTINUOUSLY while either is being
  // rotated / zoomed / panned. The live camera during a drag lives on the
  // scene's internal object (layout.scene.camera only updates on release), and
  // 'plotly_relayouting' (not 'plotly_relayout') is the event that fires
  // throughout the gesture — using those two is what makes it move in real time.
  var a = document.getElementById(idA), b = document.getElementById(idB);
  // Only the cube the user is actively driving pushes its camera to the other —
  // the passive one ignores its own (programmatic) updates, so the two never
  // feed back into each other.
  var active = null, wheelTimer = null;
  function liveCam(gd) {
    try {
      var s = gd._fullLayout && gd._fullLayout.scene && gd._fullLayout.scene._scene;
      if (s && s.getCamera) return s.getCamera();
    } catch (e) {}
    return gd.layout && gd.layout.scene && gd.layout.scene.camera;
  }
  function arm(gd) {                          // wheel has no mouseup — auto-disarm
    active = gd;
    if (wheelTimer) clearTimeout(wheelTimer);
    wheelTimer = setTimeout(function() { active = null; }, 300);
  }
  a.addEventListener("mousedown", function() { active = a; }, true);
  b.addEventListener("mousedown", function() { active = b; }, true);
  window.addEventListener("mouseup", function() { active = null; }, true);
  a.addEventListener("wheel", function() { arm(a); }, true);
  b.addEventListener("wheel", function() { arm(b); }, true);
  function link(src, dstId) {
    function sync() {
      if (active !== src) return;            // only the driven cube leads
      var c = liveCam(src);
      if (c) Plotly.relayout(dstId, {"scene.camera": c});
    }
    src.on("plotly_relayouting", sync);      // continuous, during the gesture
    src.on("plotly_relayout", sync);         // and the final committed position
  }
  link(a, idB); link(b, idA);
}
"""


def build_cube_html(
    program: list[tuple[float, ...]],
    plotly_js_url: str,
    *,
    existing_program: list[tuple[float, ...]] | None = None,
    bg: str = "#111111",
    fg: str = "#cccccc",
    grid: str = "#444444",
    numbered: bool = False,
) -> str:
    """Return a self-contained HTML page plotting ``program`` as a 3D RGB cube.

    ``plotly_js_url`` is the ``file://`` (or http) URL of the bundled
    ``plotly-gl3d.min.js``. Markers sit at each patch's (R, G, B) on the 0..100
    axes and are painted in that patch's own colour; a wireframe cube and a
    black→white neutral axis are drawn for reference. ``bg`` / ``fg`` / ``grid``
    theme the page so it matches the host dialog's light / dark appearance.

    ``existing_program`` (the editor's Add flow) is drawn dimmed underneath the
    freshly generated ``program``. The page also exposes ``window.cqUpdateCube``
    so a host can push a new :func:`cube_payload` via ``Plotly.react`` and have
    the cube redraw in place — no reload — as generator settings change.
    """
    import html as _html
    data = cube_traces(program, existing_program, fg=fg, grid=grid, numbered=numbered)
    stats_text = combined_summary(program, existing_program)
    layout = _cube_layout(bg, fg, grid)
    config = {"displaylogo": False, "responsive": True, "scrollZoom": True}
    hint = _html.escape(_controls_hint())

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="{plotly_js_url}"></script>
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; width: 100%;
                overflow: hidden; background: {bg};
                font-family: Menlo, Consolas, "Courier New", monospace; }}
  #help {{ height: 22px; line-height: 22px; color: {fg}; font-size: 10px;
           opacity: 0.75; padding: 0 10px; background: {bg}; text-align: center;
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  #plot {{ width: 100%; height: calc(100% - 26px - 22px); overflow: hidden; }}
  #stats {{ height: 26px; line-height: 26px; color: {fg}; font-size: 11px;
            padding: 0 10px; background: {bg};
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
</style></head>
<body>
  <div id="help">{hint}</div>
  <div id="plot"></div>
  <div id="stats">{stats_text}</div>
  <script>
    {_CUBE_JS_HELPERS}
    var CQ_LAYOUT = {json.dumps(layout)};
    var CQ_CONFIG = {json.dumps(config)};
    Plotly.newPlot("plot", {json.dumps(data)}, CQ_LAYOUT, CQ_CONFIG);
    cqInstallPan("plot"); cqInstallKeys("plot");
    // Live in-place update: the host pushes a {{data, stats}} payload and the
    // cube redraws via Plotly.react without reloading the page or the WebGL
    // context (see workflow.patch_cube.cube_payload).
    window.cqUpdateCube = function(payload) {{
      // A payload may carry its own layout (the Lab-space view for multi-ink
      // charts, #72); without one the RGB-cube layout stays in force.
      Plotly.react("plot", payload.data, payload.layout || CQ_LAYOUT, CQ_CONFIG);
      var s = document.getElementById("stats");
      if (s) {{ s.textContent = payload.stats; }}
    }};
  </script>
</body></html>
"""


def build_dual_cube_html(
    program_a: list[tuple[float, ...]],
    label_a: str,
    program_b: list[tuple[float, ...]],
    label_b: str,
    plotly_js_url: str,
    *,
    existing_a: list[tuple[float, ...]] | None = None,
    bg: str = "#111111",
    fg: str = "#cccccc",
    grid: str = "#444444",
    numbered_a: bool = False,
) -> str:
    """Two side-by-side 3D RGB cubes (current chart vs. a comparison preset),
    with their cameras locked in sync — rotate/zoom/pan one and the other
    follows, so they can be compared from any angle (#66). Each cube carries its
    name above it and its own stats below."""
    import html as _html
    data_a = cube_traces(program_a, existing_a, fg=fg, grid=grid, numbered=numbered_a)
    data_b = cube_traces(program_b, None, fg=fg, grid=grid)
    layout = _cube_layout(bg, fg, grid)
    config = {"displaylogo": False, "responsive": True, "scrollZoom": True}
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="{plotly_js_url}"></script>
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; width: 100%;
                overflow: hidden; background: {bg};
                font-family: Menlo, Consolas, "Courier New", monospace; }}
  #help {{ height: 22px; line-height: 22px; color: {fg}; font-size: 10px;
           opacity: 0.75; padding: 0 10px; background: {bg}; text-align: center;
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  #row {{ display: flex; width: 100%; height: calc(100% - 22px); }}
  .col {{ flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; }}
  .col + .col {{ border-left: 1px solid {grid}; }}
  .title {{ height: 24px; line-height: 24px; color: {fg}; font-size: 12px;
            font-weight: bold; text-align: center; background: {bg};
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            padding: 0 8px; }}
  .cube {{ flex: 1 1 auto; min-height: 0; }}
  .stats {{ height: 24px; line-height: 24px; color: {fg}; font-size: 11px;
            padding: 0 10px; background: {bg};
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
</style></head>
<body>
  <div id="help">{_html.escape(_controls_hint())}</div>
  <div id="row">
    <div class="col">
      <div class="title">{_html.escape(label_a)}</div>
      <div id="plotA" class="cube"></div>
      <div class="stats">{combined_summary(program_a, existing_a)}</div>
    </div>
    <div class="col">
      <div class="title">{_html.escape(label_b)}</div>
      <div id="plotB" class="cube"></div>
      <div class="stats">{combined_summary(program_b, None)}</div>
    </div>
  </div>
  <script>
    {_CUBE_JS_HELPERS}
    var CQ_LAYOUT = {json.dumps(layout)};
    var CQ_CONFIG = {json.dumps(config)};
    Promise.all([
      Plotly.newPlot("plotA", {json.dumps(data_a)}, CQ_LAYOUT, CQ_CONFIG),
      Plotly.newPlot("plotB", {json.dumps(data_b)}, CQ_LAYOUT, CQ_CONFIG)
    ]).then(function() {{
      cqInstallPan("plotA"); cqInstallPan("plotB");
      cqInstallKeys("plotA"); cqInstallKeys("plotB");   // both move together
      cqLinkCameras("plotA", "plotB");   // rotate/zoom/pan stay in sync
    }});
  </script>
</body></html>
"""
