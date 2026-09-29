"""Markdown summary of a research benchmark run (Agent 6)."""
from __future__ import annotations

from pathlib import Path

ENGINE_ORDER = ["colprof", "fast", "argyll", "accurate", "accurate@f00-parent"]


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
         f"master tree `{env.get('master_tree_commit')}`; Argyll {env['argyll']}; "
         f"lcms {env['lcms']}; numpy {env['numpy']}; {env['cpu']}; "
         f"load average at start {tuple(round(x, 1) for x in env['loadavg_start'])}.",
         "Timings are NOT controlled measurements (two builds ran in parallel).", ""]
    idn = results["identity"]
    L.append("## Hard rule 1: Fast and Bit-exact byte-identical to master")
    if not idn["compared"] and not idn["failures"]:
        L.append("Not checked in this run.")
    else:
        L.append(f"{len(idn['compared'])} profile pairs compared (v2 file and v4 twin): "
                 + ("**ALL IDENTICAL**" if not idn["failures"] else
                    "**DIFFERENCES FOUND**"))
        L += [f"* FAIL: {f}" for f in idn["failures"]]
    L.append("")
    gt = results["gates"]
    L.append("## Hard rule 2: accurate builds CMY+N and ICC v4")
    L.append(f"{len(gt['checked'])} accurate builds checked (v2 + v4 twin, iccdump, "
             "littleCMS, ColorSync): " + ("**ALL PASS**" if not gt["failures"]
                                          else "**FAILURES**"))
    L += [f"* FAIL: {f}" for f in gt["failures"]]
    L.append("")
    for reader in ("argyll", "lcms", "colorsync", "multilinear"):
        L.append(f"## dE00 by engine, read through `{reader}`")
        L.append("")
        L.append("| dataset | variant | engine | A2B med | A2B p95 | A2B max | B2A med | "
                 "B2A p95 | RT med | neutral med | neutral C*max | shadow B2A med | "
                 "hi-light B2A med (L*>85 sample) | white ink % | black L* | build s |")
        L.append("|" + "---|" * 16)
        for d in results["datasets"]:
            for eng in sorted(d["profiles"], key=lambda e: ENGINE_ORDER.index(e)
                              if e in ENGINE_ORDER else 99):
                p = d["profiles"][eng]
                if not p.get("ok"):
                    L.append(f"| {d['name']} | {d['variant']} | {eng} | build failed: "
                             f"{(p.get('error') or '')[:80].replace('|', '/')} |" + " |" * 12)
                    continue
                s = p.get("scores", {}).get(reader, {})
                a2b = s.get("a2b") or s.get("a2b_heldout") or {}
                L.append("| " + " | ".join([
                    d["name"] + (" (held-out)" if d["kind"] == "real" else ""),
                    d["variant"], eng,
                    _g(a2b, "all", "median"), _g(a2b, "all", "p95"), _g(a2b, "all", "max", fmt="{:.2f}"),
                    _g(s, "b2a", "all", "median"), _g(s, "b2a", "all", "p95"),
                    _g(s, "roundtrip", "median"),
                    _g(s, "neutral", "de", "median"), _g(s, "neutral", "chroma_max", fmt="{:.2f}"),
                    _g(s, "b2a", "shadow_L<20", "median"),
                    _g(s, "b2a", "highlight_sample", "median"),
                    _g(s, "white", "max_ink_pct", fmt="{:.2f}"),
                    _g(s, "black", "printed_L", fmt="{:.2f}"),
                    _g(p, "seconds", fmt="{:.0f}")]) + " |")
        L.append("")
    L.append("Real datasets: A2B is scored at held-out patches (measured, noisy); "
             "B2A/neutral are printed through a PROXY printer (colprof -qh of all "
             "patches), an estimate, not truth.")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")
