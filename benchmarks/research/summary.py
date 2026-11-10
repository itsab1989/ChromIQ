"""Markdown summary of a research benchmark run (Agent 6)."""
from __future__ import annotations

from pathlib import Path

from benchmarks.research.datasets import ROBUSTNESS_LABEL, ROBUSTNESS_ONLY, is_robustness_only

ENGINE_ORDER = ["colprof", "fast", "argyll", "accurate", "fast@upstream",
                "argyll@upstream", "accurate@f00-parent"]


def _g(d, *keys, fmt="{:.3f}"):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return "n/a"
        d = d[k]
    if d is None:
        return "n/a"
    return fmt.format(d) if isinstance(d, (int, float)) else str(d)


def write_summary(results: dict, path: Path) -> None:
    env = results["env"]
    L = [f"# Research benchmark run, {env['time']}", "",
         f"Commit `{env['commit']}` ({env['branch']}), dirty: {'yes' if env['dirty'] else 'no'}; "
         f"identity ref `{env.get('identity_tree_commit')}`; upstream (master) "
         f"`{env.get('upstream_tree_commit')}`; Argyll {env['argyll']}; "
         f"lcms {env['lcms']}; numpy {env['numpy']}; {env['cpu']}; "
         f"load average at start {tuple(round(x, 1) for x in env['loadavg_start'])}.",
         "Timings are NOT controlled measurements (two builds ran in parallel).", ""]
    idn = results["identity"]
    L.append("## Hard rule 1: Fast and Bit-exact byte-identical to the identity reference (D-02)")
    if not idn["compared"] and not idn["failures"]:
        L.append("Not checked in this run.")
    else:
        L.append(f"{len(idn['compared'])} profile pairs compared (v2 file and v4 twin): "
                 + ("**ALL IDENTICAL**" if not idn["failures"] else
                    "**DIFFERENCES FOUND**"))
        L += [f"* FAIL: {f}" for f in idn["failures"]]
    L.append("")
    up = results.get("upstream") or {}
    if up.get("compared") or up.get("errors"):
        L.append("## Master's Fast / Bit-exact, measured (not a gate)")
        L.append("")
        L.append("| profile | tags that differ (v2) | v4 twin tags | A2B dE00 med / p95 / max | "
                 "B2A device max-channel med / p95 / max | paper white branch / master |")
        L.append("|---|---|---|---|---|---|")
        for r in up.get("compared", []):
            v2 = r.get("v2") or {}
            if not v2:
                L.append(f"| {r['profile']} | error: {r.get('error', '')[:80]} | | | | |")
                continue
            a, d = v2["a2b_de00"], v2["b2a_device_maxch"]
            L.append(f"| {r['profile']} | {' '.join(v2['tags']) or 'none'} | "
                     f"{' '.join((r.get('v4_tags') or {}).get('tags', [])) or 'none'} | "
                     f"{a['median']:.4f} / {a['p95']:.4f} / {a['max']:.3f} | "
                     f"{d['median']:.4f} / {d['p95']:.4f} / {d['max']:.3f} | "
                     f"{v2['white_a']} / {v2['white_b']} |")
        L += [f"* {e}" for e in up.get("errors", [])]
        L.append("")
    gt = results["gates"]
    L.append("## Hard rule 2: accurate builds CMY+N and ICC v4")
    L.append(f"{len(gt['checked'])} accurate builds checked (v2 + v4 twin, iccdump, "
             "littleCMS, ColorSync): " + ("**ALL PASS**" if not gt["failures"]
                                          else "**FAILURES**"))
    L += [f"* FAIL: {f}" for f in gt["failures"]]
    L.append("")
    L.append("Datasets marked (dev) are DEVELOPMENT sets (protocol v2 section 1a): "
             "the engine was tuned on them; a claim of 'better' rests on the "
             "confirmatory sets only. Sets marked "
             f"({ROBUSTNESS_LABEL}) are non-representative real data: "
             + ", ".join(ROBUSTNESS_ONLY) + ".")
    L.append("")
    readers = []
    for d in results["datasets"]:
        for p in d["profiles"].values():
            readers += [r for r in (p.get("scores") or {}) if r not in readers]
    for reader in readers or ("argyll", "lcms", "colorsync", "multilinear"):
        L.append(f"## dE00 by engine, read through `{reader}`")
        L.append("")
        L.append("| dataset | variant | engine | A2B med | A2B p95 | A2B max | B2A med | "
                 "B2A p95 | RT med | neutral med | neutral C*max | neutral L*>=85 mean | L*93.75 prints | shadow B2A med | "
                 "hi-light B2A med (L*>85 sample) | white ink % | black L* | build s |")
        L.append("|" + "---|" * 18)
        for d in results["datasets"]:
            for eng in sorted(d["profiles"], key=lambda e: ENGINE_ORDER.index(e)
                              if e in ENGINE_ORDER else 99):
                p = d["profiles"][eng]
                if not p.get("ok"):
                    L.append(f"| {d['name']} | {d['variant']} | {eng} | build failed: "
                             f"{(p.get('error') or '')[:80].replace('|', '/')} |" + " |" * 14)
                    continue
                s = p.get("scores", {}).get(reader, {})
                a2b = s.get("a2b") or s.get("a2b_heldout") or {}
                L.append("| " + " | ".join([
                    d["name"] + (" (held-out)" if d["kind"] == "real" else "")
                    + (" (dev)" if d.get("role") == "development" else "")
                    + (f" ({ROBUSTNESS_LABEL})" if is_robustness_only(d["name"]) else ""),
                    d["variant"], eng,
                    _g(a2b, "all", "median"), _g(a2b, "all", "p95"), _g(a2b, "all", "max", fmt="{:.2f}"),
                    _g(s, "b2a", "all", "median"), _g(s, "b2a", "all", "p95"),
                    _g(s, "roundtrip", "median"),
                    _g(s, "neutral", "de", "median"), _g(s, "neutral", "chroma_max", fmt="{:.2f}"),
                    _g(s, "neutral", "highlight", "de", "mean"),
                    _g(s, "neutral", "highlight", "printed_L_at_93_75", fmt="{:.1f}"),
                    _g(s, "b2a", "shadow_L<20", "median"),
                    _g(s, "b2a", "highlight_sample", "median"),
                    _g(s, "white", "max_ink_pct", fmt="{:.2f}"),
                    _g(s, "black", "printed_L", fmt="{:.2f}"),
                    _g(p, "seconds", fmt="{:.0f}")]) + " |")
        L.append("")
    L.append("Real datasets: A2B is scored at held-out patches (measured, noisy); "
             "B2A/neutral are printed through a PROXY printer (colprof -qh of all "
             "patches; for 5+ inks, which colprof refuses, the set's own published "
             "reference profile, which saw every patch), an estimate, not truth.")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")
