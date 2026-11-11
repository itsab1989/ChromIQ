# Vendored ArgyllCMS sources

These files are a subset of **ArgyllCMS 3.5.0** by Graeme W. Gill,
copied verbatim from the official source distribution. They are licensed under
the **GNU Affero General Public License v3** (see LICENSE).

- Upstream: https://www.argyllcms.com/  (Argyll_V3.5.0)
- Subset: the 45 translation units + 114 headers required to build
  ChromIQ's bit-exact gamut-mapping helper (numlib, icc, cgats, rspl,
  gamut, xicc, plus spectro/conv and plot/vrml).
- ONE source change (F-08, 2026-10-05): `gamut/gamut.c`, `radial_point_triang`
  and `vector_isect_rec` read a single-triangle BSP leaf through
  `(gtri **)&np`, a strict-aliasing violation. Clang >= 20 (pointer TBAA on by
  default) deletes the store of `np` at -O2/-O3 and the helper segfaults. Both
  sites now copy the pointer into a real `gtri *t1` and point `tpp` at it. The
  helper is also compiled with `-fno-strict-aliasing` (CMakeLists.txt). Output
  is byte-identical to the unpatched source wherever that did not crash.
  Reported for upstream. Every other file is unchanged.
- To bump: re-copy the same file list from the new
  Argyll release and re-verify the helper builds byte-identical.
