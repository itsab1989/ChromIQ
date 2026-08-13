"""Put freshly captured screenshots into the landing page (docs/index.html).

The page inlines every image as base64 webp, so there are no image files to
replace -- this rewrites the `src` of the ones we own and leaves the rest
alone. Run it after capture_screens.py has produced a landing set:

    source .venv/bin/activate
    # 1. shoot the landing set (its own framing, its own output folder)
    CHROMIQ_SHOTS_OUT=/tmp/landing CHROMIQ_SHOTS_CLEAN_PREVIEW=1 \
        python scripts/capture_screens.py
    # 2. splice it in
    python scripts/splice_landing_shots.py /tmp/landing
    # 3. check, then commit docs/index.html

It refuses to write unless it finds exactly the 11 inline images it expects,
so a page that has been restructured fails loudly instead of being mangled.

Sebastian's brief:
  * the big hero shot: Create Chart **Guided**, as a dark/light pair the page
    swaps by the visitor's own theme (light mode gets the light one);
  * every other shot dark, and the Create Chart one among them **Manual**;
  * the Print Chart shot showing ChromIQ's own printing pipeline with the
    Canon PRO-300 selected and the print options visible — not the native
    macOS dialog;
  * the Measure shot showing the expected-vs-measured overlay;
  * Create Chart shots taken with the three Preferences ▸ Instrument Limits
    checkboxes off, so nothing is drawn over the sheet.

The scanner-profiling shot and the ChromIQ Patches shot are left exactly as
they are, and so are the two icon chips.
"""
import base64
import io
import pathlib
import re
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAND = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("/tmp/landing")
DOCS = ROOT / "docs"
PAGE = DOCS / "index.html"

# Document-order image index → (source, width, quality).
# The hero spans the 1140 px content column, so 2400 px covers a 2x screen; the
# step shots are declared width="760" and get 2000 px, comfortably over 2x.
PLAN = {
    1: (LAND / "01-create-chart-guided-dark.png",   2400, 92),   # hero, dark
    2: (LAND / "01-create-chart-guided-light.png",  2400, 92),   # hero, light
    3: (LAND / "02-create-chart-manual-dark.png",   2000, 92),
    4: (LAND / "04-print-chart-postscript-dark.png", 2000, 92),
    5: (LAND / "06b-measure-overlay-dark.png",      2000, 92),
    6: (LAND / "07-build-profile-guided-dark.png",  2000, 92),
    7: (LAND / "13-gamut-compare-dark.png",         2000, 92),
}
KEEP = {0: "icon chip", 8: "scanner profiling", 9: "ChromIQ Patches", 10: "icon chip"}

def encode(png: pathlib.Path, width: int, quality: int) -> tuple[str, int]:
    im = Image.open(png).convert("RGB")
    if im.width != width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=quality, method=6)
    raw = buf.getvalue()
    return base64.b64encode(raw).decode("ascii"), len(raw)


def main() -> int:
    if not LAND.is_dir():
        print(f"no landing set at {LAND} -- run capture_screens.py with "
              f"CHROMIQ_SHOTS_OUT={LAND} CHROMIQ_SHOTS_CLEAN_PREVIEW=1 first")
        return 1
    html = PAGE.read_text()
    before = len(html)

    # Swap in the fresh screenshots.
    tags = list(re.finditer(r'<img[^>]*src="data:image/(?:png|webp);base64,([^"]+)"[^>]*>',
                            html))
    if len(tags) != 11:
        print(f"expected 11 inline images, found {len(tags)}")
        return 1
    for i, (src, _w, _q) in PLAN.items():
        if not src.is_file():
            print(f"missing source for image {i}: {src}")
            return 1

    out, cursor, total = [], 0, 0
    for i, m in enumerate(tags):
        out.append(html[cursor:m.start()])
        tag = m.group(0)
        if i in PLAN:
            src, w, q = PLAN[i]
            b64, nbytes = encode(src, w, q)
            tag = re.sub(r'src="data:image/(?:png|webp);base64,[^"]+"',
                         f'src="data:image/webp;base64,{b64}"', tag, count=1)
            total += nbytes
            print(f"  [{i}] {src.name:<38} -> {w}px q{q}  {nbytes/1024:6.0f} KB")
        else:
            print(f"  [{i}] kept: {KEEP.get(i, '?')}")
        out.append(tag)
        cursor = m.end()
    out.append(html[cursor:])
    new = "".join(out)

    # The two captions whose subject changed.
    swaps = [
        ('alt="Native print dialog with colour management locked"',
         'alt="ChromIQ printing the chart itself, with the Canon PRO-300 '
         'selected and the print options shown"'),
        ("<figcaption>Native print dialog with colour management locked</figcaption>",
         "<figcaption>ChromIQ&rsquo;s own printing pipeline, colour management "
         "off</figcaption>"),
        ('alt="Guided strip-by-strip measurement"',
         'alt="Measuring a chart, each patch split between the colour expected '
         'and the colour measured"'),
        ("<figcaption>Guided strip-by-strip measurement</figcaption>",
         "<figcaption>Guided strip-by-strip measurement, expected against "
         "measured</figcaption>"),
    ]
    for old, repl in swaps:
        if old in new:
            new = new.replace(old, repl)
        elif repl not in new:
            # Neither the original wording nor ours: the page has been edited
            # by hand and this script no longer knows what it is looking at.
            print(f"caption not found, and not already updated: {old[:60]}")
            return 1
    print("  captions: print and measure say what those shots now show")

    PAGE.write_text(new)
    print(f"\n  replaced {len(PLAN)} images, {total/1024:.0f} KB of webp")
    print(f"  page is now {len(new)/1024:.0f} KB (was {before/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
