"""Printer detection and option querying via CUPS."""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from typing import Optional

from core.logger import get_logger
from core.name_order import sort_names
from core.proc_text import run_text
from core.text_io import read_text
from workflow.cups_printer import CUPS_AVAILABLE, PrintConfig

if CUPS_AVAILABLE:
    import cups as _cups_mod  # type: ignore[import]

log = get_logger(__name__)

# Synthetic option name used to surface a clean Yes/No "Borderless" toggle in
# the UI when the driver only encodes borderless inside PageSize variants or
# multi-choice options like EPIJ_PSrc. Resolved back to real lp options in
# build_config().
_BORDERLESS_SYNTH = "__BORDERLESS__"
# Suffixes printers append to a base PageSize value to mean "borderless".
_BORDERLESS_SIZE_SUFFIXES = (".NMgn", ".Borderless", ".FullBleed", "Borderless", "FullBleed")
# Option names whose 3-value (Borderless) choice toggles borderless mode.
_EPSON_PSRC_OPT = "EPIJ_PSrc"
_EPSON_PSRC_STANDARD = "2"
_EPSON_PSRC_BORDERLESS = "3"


class PrintModule:
    """Detect installed printers and query their supported options."""

    def __init__(self) -> None:
        # Per-printer borderless resolution state, populated by query_options
        # and consumed by build_config to translate __BORDERLESS__ back into
        # real lp options before submission.
        # value shape: {
        #   "kind": "epij_psrc" | "pagesize_variant",
        #   "size_opt": <CUPS option name carrying the size variant> (variant kind only),
        #   "variant_map": { base_raw: borderless_raw },                (variant kind only),
        # }
        self._borderless_state: dict[str, dict] = {}

    def detect_printers(self) -> list[str]:
        """Return filtered list of non-AirPrint printer names from CUPS."""
        if not CUPS_AVAILABLE:
            return []
        try:
            conn = _cups_mod.Connection()
            result: list[str] = []
            for name, attrs in conn.getPrinters().items():
                model = attrs.get("printer-make-and-model", "")
                if "airprint" in model.lower() or "airprint" in name.lower():
                    continue
                result.append(name)
            # ONE rule for name order (core.name_order): a plain sort() is
            # byte-by-byte, so a queue called "brother_HL5450" landed below
            # every printer whose name starts with a capital instead of beside
            # the other b's.
            result = sort_names(result)
            log.debug("Detected printers: %s", result)
            return result
        except Exception as exc:
            log.warning("detect_printers error: %s", exc)
            return []

    # For each print setting category:
    # (exact_cups_names_to_try_first, label_keywords_as_fallback)
    # IMPORTANT: exact_names is a tuple (not a set) so iteration order is
    # deterministic across Python invocations (sets are hash-randomised).
    # Vendor-specific names come first so they are preferred when both a
    # vendor name and a generic name exist (e.g. Epson has both EPIJ_Medi
    # and MediaType — we want EPIJ_Medi to win for correct rule matching).
    _CATEGORY_SEARCHES: list[tuple[tuple[str, ...], list[str]]] = [
        (
            ("EPIJ_FdSo", "CNPaperSource", "InputSlot"),
            ["input slot", "paper source", "feed source", "tray", "cassette"],
        ),
        (
            ("EPIJ_Size", "media", "PageSize"),
            ["paper size", "media size", "page size"],
        ),
        (
            ("EPIJ_Medi", "CNMediaType", "BrMediaType", "media-type", "MediaType"),
            ["media type", "paper type", "media kind"],
        ),
        (
            (
                "EPIJ_Qual", "CNQuality", "BrQuality",
                "OutputMode", "HPOutputMode", "PrintoutMode",
                "cupsPrintQuality", "print-quality",
            ),
            ["print quality", "output quality", "quality mode", "printout mode"],
        ),
        (
            ("EPIJ_Brlss", "CNBorderless", "BorderlessPrint", "Borderless"),
            ["borderless", "edge to edge", "full bleed"],
        ),
    ]

    # IPP standard integer quality codes used by driverless/IPP-Everywhere printers.
    _IPP_QUALITY_LABELS: dict[str, str] = {"3": "Draft", "4": "Normal", "5": "High"}

    # Fallback labels for binary borderless toggles whose PPD doesn't declare nice
    # labels (Epson EPIJ_Brlss is the common case — raw values are True/False).
    _BORDERLESS_LABELS: dict[str, str] = {
        "True":  "Yes",
        "False": "No",
        "On":    "Yes",
        "Off":   "No",
    }

    # All option names that represent print quality (used by filtering logic).
    _QUALITY_OPT_NAMES: frozenset[str] = frozenset({
        "print-quality", "EPIJ_Qual", "CNQuality", "BrQuality",
        "OutputMode", "HPOutputMode", "PrintoutMode", "cupsPrintQuality",
    })

    # Option names representing borderless toggles.
    _BORDERLESS_OPT_NAMES: frozenset[str] = frozenset({
        "EPIJ_Brlss", "CNBorderless", "BorderlessPrint", "Borderless",
    })

    # Option names representing a feed source / paper tray.
    _PAPER_SOURCE_OPT_NAMES: frozenset[str] = frozenset({
        "EPIJ_FdSo", "CNPaperSource", "InputSlot",
    })

    # Option names representing a paper size (vendor + standard).
    _PAPER_SIZE_OPT_NAMES: frozenset[str] = frozenset({
        "EPIJ_Size", "PageSize", "media", "media-size",
    })

    # Cassette-label keyword groups used to filter paper sizes after the
    # user picks a feed source. Comparison is case-insensitive substring.
    _CASSETTE_OPEN_KEYWORDS: tuple[str, ...] = (
        # "Auto" lets the driver decide → never filter.
        "auto",
        # Rear / manual / specialty / multi-purpose feeds accept everything,
        # including A3 / A3+ / large format.
        "rear", "manual", "bypass", "multi", "specialty",
        "mp tray", "mp-tray", "mptray",
    )
    _CASSETTE_PHOTO_KEYWORDS: tuple[str, ...] = (
        "photo",
    )
    _CASSETTE_STANDARD_KEYWORDS: tuple[str, ...] = (
        "cassette", "tray", "drawer", "front",
    )

    # Display-label substrings (case-insensitive) that mark a paper size as
    # too large for a standard front cassette. Conservative — only filters
    # well-known oversize formats.
    _OVERSIZE_LABEL_KEYWORDS: tuple[str, ...] = (
        "a3", "a3+", "super b",
        "b4", "jis b4",
        "tabloid", "11 x 17", "11x17",
        "12 x 18", "12x18", "13 x 19", "13x19",
        "8k",
    )

    # Display-label substrings that mark a paper size as a small photo media.
    _PHOTO_SIZE_KEYWORDS: tuple[str, ...] = (
        "4 x 6", "4x6", "5 x 7", "5x7", "3.5", "3,5",
        "9 x 13", "9x13", "10 x 15", "10x15", "13 x 18", "13x18",
        "100 x 148", "100x148", "hagaki",
        "16:9",
        "a6", "a7",
        "stickers",
        "card", "postcard",
    )

    # Exact allowlists for Epson EPIJ printers, keyed by raw EPIJ_Medi value.
    # Derived from the actual combinations the Epson ET-8550 driver presents in its
    # print dialog. The raw values are stable and language-independent.
    # EPIJ_Qual raw values: 302=Economy, 303=Normal, 308=Draft, 304=Fine,
    #                       305=Quality, 306=High Quality, 307=Best Quality
    _EPSON_QUALITY_RULES: dict[str, frozenset[str]] = {
        "0":   frozenset({"302", "303", "304", "307"}),  # Plain paper
        "142": frozenset({"302", "303", "304", "307"}),  # Letterhead
        "2":   frozenset({"305", "306"}),               # Epson Photo Quality Ink Jet
        "12":  frozenset({"305", "306"}),               # Epson Matte
        "92":  frozenset({"305", "306", "307"}),        # Epson Ultra Glossy
        "13":  frozenset({"308", "305", "306"}),        # Epson Premium Glossy
        "15":  frozenset({"308", "305", "306"}),        # Epson Premium Semigloss
        "145": frozenset({"308", "305", "306"}),        # Photo Paper Glossy
        "75":  frozenset({"305"}),                      # Epson Photo Stickers
        "93":  frozenset({"303", "304"}),               # Envelope
        "187": frozenset({"306"}),                      # Thin paper
        "159": frozenset({"306"}),                      # Thick paper 1 (0.8 mm)
        "160": frozenset({"306"}),                      # Thick paper 2 (1.3 mm)
    }

    def query_options(self, printer: str) -> dict[str, tuple[str, list[tuple[str, str]]]]:
        """Return up to 4 CUPS options covering the standard print settings.

        Checks exact CUPS option names first, then falls back to label-keyword
        matching — so both standard CUPS drivers and vendor-specific drivers
        (e.g. EPSON EPIJ_*) are handled correctly.
        Values are looked up in the printer's PPD file so human-readable names
        are shown instead of raw codes.
        Returns dict: CUPS_option_name → (category_label, [(display_label, raw_cups_value), ...]).
        """
        result: dict[str, tuple[str, list[tuple[str, str]]]] = {}
        if not CUPS_AVAILABLE:
            return result
        try:
            r = run_text(
                ["lpoptions", "-p", printer, "-l"],
                capture_output=True, timeout=15,
                stdin=subprocess.DEVNULL,
            )
            # Parse all options: opt_name → (label, [raw_value, ...])
            all_opts: dict[str, tuple[str, list[str]]] = {}
            for line in r.stdout.splitlines():
                if ":" not in line:
                    continue
                key_part, vals_part = line.split(":", 1)
                key_part = key_part.strip()
                opt_name  = key_part.split("/")[0].strip()
                opt_label = key_part.split("/")[1].strip() if "/" in key_part else opt_name
                vals = [v.lstrip("*") for v in vals_part.split() if v.strip()]
                if len(vals) >= 2:
                    all_opts[opt_name] = (opt_label, vals)

            ppd_labels = self._parse_ppd_labels(printer)

            # For each category, pick the first matching option
            for exact_names, label_keywords in self._CATEGORY_SEARCHES:
                matched_name: str | None = None
                for name in exact_names:
                    if name in all_opts:
                        matched_name = name
                        break
                if matched_name is None:
                    for opt_name, (opt_label, _) in all_opts.items():
                        if any(kw in opt_label.lower() for kw in label_keywords):
                            matched_name = opt_name
                            break

                if matched_name is not None:
                    opt_label, raw_vals = all_opts[matched_name]
                    val_labels = ppd_labels.get(matched_name, {})
                    # For quality options with no PPD label, map IPP integers to names.
                    if matched_name in self._QUALITY_OPT_NAMES:
                        for v in raw_vals:
                            if v not in val_labels and v in self._IPP_QUALITY_LABELS:
                                val_labels[v] = self._IPP_QUALITY_LABELS[v]
                    # For borderless toggles with no PPD label, map True/False/On/Off.
                    if matched_name in self._BORDERLESS_OPT_NAMES:
                        for v in raw_vals:
                            if v not in val_labels and v in self._BORDERLESS_LABELS:
                                val_labels[v] = self._BORDERLESS_LABELS[v]
                    # Pair each raw CUPS value with its human-readable display label
                    pairs = [(val_labels.get(v, v), v) for v in raw_vals]
                    result[matched_name] = (opt_label, pairs)

            # Driver-aware borderless synthesis. Runs only when no real
            # borderless option was already matched as the 5th category, so
            # explicit EPIJ_Brlss / CNBorderless drivers keep their native
            # toggle. Detects two encodings:
            #   1. Multi-choice "page setup" options where a "3" value means
            #      borderless (e.g. Epson EPIJ_PSrc).
            #   2. PageSize values that have .NMgn / .Borderless / .FullBleed
            #      variants (most CUPS/PWG drivers; queried directly from
            #      lpoptions so it works even when the UI shows a vendor size
            #      option like EPIJ_Size instead of PageSize).
            self._borderless_state.pop(printer, None)
            already_native = any(
                k in self._BORDERLESS_OPT_NAMES for k in result.keys()
            )
            if not already_native:
                synth = self._synthesize_borderless(printer, all_opts, ppd_labels, result)
                if synth is not None:
                    state, pair_label, pair_values = synth
                    self._borderless_state[printer] = state
                    result[_BORDERLESS_SYNTH] = (pair_label, pair_values)

        except Exception as exc:
            log.warning("query_options(%s) error: %s", printer, exc)

        result = self._reorder_for_display(result)
        log.debug("Options for %s: %d configurable options", printer, len(result))
        return result

    @classmethod
    def _reorder_for_display(
        cls,
        result: dict[str, tuple[str, list[tuple[str, str]]]],
    ) -> dict[str, tuple[str, list[tuple[str, str]]]]:
        """Place the borderless option right after the paper-size option.

        Categories are otherwise discovered in this order: paper source, paper
        size, media type, quality, borderless — but borderless reads more
        naturally next to paper size in the UI.  Everything else keeps its
        relative order.  If there is no paper-size option, borderless stays last.
        """
        keys = list(result.keys())
        borderless = [
            k for k in keys
            if k in cls._BORDERLESS_OPT_NAMES or k == _BORDERLESS_SYNTH
        ]
        if not borderless:
            return result
        rest = [k for k in keys if k not in borderless]
        insert_at = len(rest)
        for i, k in enumerate(rest):
            if k in cls._PAPER_SIZE_OPT_NAMES:
                insert_at = i + 1
                break
        new_order = rest[:insert_at] + borderless + rest[insert_at:]
        return {k: result[k] for k in new_order}

    def _synthesize_borderless(
        self,
        printer: str,
        all_opts: dict[str, tuple[str, list[str]]],
        ppd_labels: dict[str, dict[str, str]],
        matched_result: dict[str, tuple[str, list[tuple[str, str]]]],
    ) -> tuple[dict, str, list[tuple[str, str]]] | None:
        """Detect implicit borderless support and return (state, label, pairs).

        Returns None when no borderless encoding is detected.
        """
        # Path 1 — Epson EPIJ_PSrc: a "Page Setup" picker that includes
        # a Borderless choice (raw value "3"). We expose it as a Yes/No
        # toggle and map Yes→3 / No→2 at submission time.
        if _EPSON_PSRC_OPT in all_opts:
            _, psrc_vals = all_opts[_EPSON_PSRC_OPT]
            if _EPSON_PSRC_BORDERLESS in psrc_vals:
                return (
                    {"kind": "epij_psrc"},
                    "Borderless",
                    [("No", "False"), ("Yes", "True")],
                )

        # Path 2 — PageSize variants with .NMgn/.Borderless/.FullBleed.
        # Try the standard PageSize option first (always present alongside
        # vendor names like EPIJ_Size); fall back to whichever size option
        # we surfaced in matched_result.
        candidate_size_opts: list[str] = []
        if "PageSize" in all_opts:
            candidate_size_opts.append("PageSize")
        for size_name in ("EPIJ_Size", "media"):
            if size_name in all_opts and size_name not in candidate_size_opts:
                candidate_size_opts.append(size_name)

        for size_opt in candidate_size_opts:
            _, size_vals = all_opts[size_opt]
            variant_map = self._build_borderless_variant_map(size_vals)
            if variant_map:
                return (
                    {
                        "kind": "pagesize_variant",
                        "size_opt": size_opt,
                        "variant_map": variant_map,
                    },
                    "Borderless",
                    [("No", "False"), ("Yes", "True")],
                )
        return None

    @staticmethod
    def _build_borderless_variant_map(values: list[str]) -> dict[str, str]:
        """Return {base_value: borderless_variant_value} for every base that
        has a matching borderless variant in *values*."""
        value_set = set(values)
        result: dict[str, str] = {}
        for v in values:
            for suffix in _BORDERLESS_SIZE_SUFFIXES:
                if v.endswith(suffix) and len(v) > len(suffix):
                    base = v[: -len(suffix)]
                    # Some drivers join without the dot (e.g. "LetterBorderless"
                    # ← "Letter"); for dotted suffixes we strip the dot.
                    base = base.rstrip(".")
                    if base in value_set:
                        result[base] = v
                    break
        return result

    def get_valid_option_values(
        self,
        printer: str,
        preceding_opts: dict[str, str],
        preceding_labels: dict[str, str],
        opt_name: str,
        all_values: list[str],
        all_pairs: list[tuple[str, str]],
    ) -> list[str]:
        """Return the subset of *all_values* that don't conflict with preceding selections.

        Priority order:
        1. Epson EPIJ exact allowlists (derived from the actual driver dialog).
        2. PPD UIConstraints via cups.PPD (for printers that define them).
        3. General keyword heuristics as a conservative fallback.
        """
        # 1. Epson EPIJ: exact allowlists keyed by raw media value.
        #    Check all possible media-type key names because query_options() may
        #    have matched "MediaType" instead of "EPIJ_Medi" (both exist on Epson).
        if opt_name == "EPIJ_Qual":
            media_raw = next(
                (v for k, v in preceding_opts.items()
                 if k in {"EPIJ_Medi", "MediaType", "media-type",
                          "CNMediaType", "BrMediaType"}),
                "",
            )
            if media_raw in self._EPSON_QUALITY_RULES:
                allowed = self._EPSON_QUALITY_RULES[media_raw]
                filtered = [rv for _, rv in all_pairs if rv in allowed]
                return filtered or [rv for _, rv in all_pairs]

        # 2. PPD UIConstraints (most printers define none for quality/media, but some do).
        ppd_path = self._find_ppd_path(printer)
        if ppd_path:
            ppd_filtered = self._filter_via_ppd(ppd_path, preceding_opts, opt_name, all_values)
            # Only trust PPD filter if it actually removed something.
            if len(ppd_filtered) < len(all_values):
                return ppd_filtered

        # 3. Paper-size filtering by feed source — Epson PPDs declare zero
        #    UIConstraints between cassette and size, so we must heuristic.
        if opt_name in self._PAPER_SIZE_OPT_NAMES:
            cassette_label = next(
                (lbl for k, lbl in preceding_labels.items()
                 if k in self._PAPER_SOURCE_OPT_NAMES),
                "",
            )
            if cassette_label:
                size_filtered = self._filter_size_by_cassette(cassette_label, all_pairs)
                if 0 < len(size_filtered) < len(all_values):
                    return size_filtered

        # 4. General heuristics for all other drivers.
        return self._filter_via_rules(preceding_labels, opt_name, all_pairs)

    @classmethod
    def _filter_size_by_cassette(
        cls,
        cassette_label: str,
        all_pairs: list[tuple[str, str]],
    ) -> list[str]:
        """Return raw size values compatible with a feed-source cassette.

        Classifies the cassette by display-label keyword and applies one of:
          • OPEN  — accept everything (Auto, Rear, Manual, Specialty, MP tray)
          • PHOTO — only small photo sizes (4×6, 5×7, A6, postcards, …)
          • FRONT — standard front cassette: exclude A3/A3+/B4/Tabloid/etc.
        Returns the unmodified list if classification is ambiguous.
        """
        cl = cassette_label.lower()
        if any(kw in cl for kw in cls._CASSETTE_OPEN_KEYWORDS):
            return [rv for _, rv in all_pairs]
        if any(kw in cl for kw in cls._CASSETTE_PHOTO_KEYWORDS):
            return [rv for disp, rv in all_pairs
                    if any(kw in disp.lower() for kw in cls._PHOTO_SIZE_KEYWORDS)]
        if any(kw in cl for kw in cls._CASSETTE_STANDARD_KEYWORDS):
            return [rv for disp, rv in all_pairs
                    if not any(kw in disp.lower() for kw in cls._OVERSIZE_LABEL_KEYWORDS)]
        return [rv for _, rv in all_pairs]

    @staticmethod
    def _find_ppd_path(printer: str) -> str | None:
        for base in ("/etc/cups/ppd", "/private/etc/cups/ppd"):
            p = pathlib.Path(f"{base}/{printer}.ppd")
            if p.exists():
                return str(p)
        return None

    @staticmethod
    def _filter_via_ppd(
        ppd_path: str,
        preceding_opts: dict[str, str],
        opt_name: str,
        all_values: list[str],
    ) -> list[str]:
        if not CUPS_AVAILABLE:
            return all_values
        try:
            ppd = _cups_mod.PPD(ppd_path)
            valid: list[str] = []
            for v in all_values:
                ppd.markDefaults()
                for k, pv in preceding_opts.items():
                    if pv:
                        ppd.markOption(k, pv)
                ppd.markOption(opt_name, v)
                if ppd.conflicts() == 0:
                    valid.append(v)
            return valid or all_values  # never block user completely
        except Exception as exc:
            log.warning("PPD constraint filter failed: %s", exc)
            return all_values

    @classmethod
    def _filter_via_rules(
        cls,
        preceding_labels: dict[str, str],
        opt_name: str,
        all_pairs: list[tuple[str, str]],
    ) -> list[str]:
        """Conservative keyword heuristics for non-Epson, non-PPD-constrained printers.

        Matches against human-readable display labels so it works across driver
        families (HP text values, IPP integers mapped to Draft/Normal/High, etc.).
        Deliberately avoids over-filtering: only excludes combinations that are
        clearly wrong (e.g. a "Photo" quality mode on plain paper).
        """
        if opt_name not in cls._QUALITY_OPT_NAMES:
            return [rv for _, rv in all_pairs]

        # Find media-type display label from whichever vendor option was selected.
        media_label = next(
            (v for k, v in preceding_labels.items()
             if k in {"EPIJ_Medi", "media-type", "MediaType", "CNMediaType", "BrMediaType"}),
            "",
        ).lower()

        if not media_label:
            return [rv for _, rv in all_pairs]

        # IPP/PWG "stationery" = plain paper; other vendors use "plain", "bond", etc.
        _PLAIN_MEDIA = (
            "plain", "stationery", "letterhead", "bond", "recycled", "standard",
        )
        # Photo/specialty media keywords.
        _PHOTO_MEDIA = (
            "photo", "glossy", "premium", "matte", "velvet",
            "silk", "luster", "pearl", "satin", "coated", "brochure",
        )

        if any(k in media_label for k in _PLAIN_MEDIA):
            # Exclude quality labels that are explicitly photo-specific modes.
            # Deliberately conservative: only "Photo" as a standalone quality label.
            return [rv for disp, rv in all_pairs
                    if disp.lower() not in ("photo",)]

        if any(k in media_label for k in _PHOTO_MEDIA):
            # Exclude explicit economy/toner-saver modes for photo media.
            _EXCLUDE = ("economy", "toner saver", "toner save", "eco")
            return [rv for disp, rv in all_pairs
                    if not any(x in disp.lower() for x in _EXCLUDE)]

        return [rv for _, rv in all_pairs]

    @staticmethod
    def _parse_ppd_labels(printer: str) -> dict[str, dict[str, str]]:
        """Parse PPD file to get human-readable labels for option values.

        Returns dict: opt_name → {raw_value → human_label}.
        """
        ppd_file = PrintModule._find_ppd_path(printer)
        if not ppd_file:
            return {}
        labels: dict[str, dict[str, str]] = {}
        try:
            pattern = re.compile(r'^\*(\S+)\s+(\S+)/([^:]+):')
            for line in read_text(pathlib.Path(ppd_file), lenient=True).splitlines():
                m = pattern.match(line)
                if m:
                    opt, val, label = m.group(1), m.group(2), m.group(3).strip()
                    labels.setdefault(opt, {})[val] = label
        except Exception:
            pass
        return labels

    def get_stuck_jobs(self, printer: str) -> list[int]:
        """Return job IDs in definitively stuck states: held=4, stopped=6, aborted=8."""
        if not CUPS_AVAILABLE:
            return []
        try:
            conn = _cups_mod.Connection()
            jobs = conn.getJobs(which_jobs="not-completed", my_jobs=False)
            stuck = []
            for job_id, attrs in jobs.items():
                if printer not in attrs.get("job-printer-uri", ""):
                    continue
                if attrs.get("job-state", 0) in (4, 6, 8):
                    stuck.append(job_id)
            return stuck
        except Exception as exc:
            log.warning("get_stuck_jobs error: %s", exc)
            return []

    def cancel_all_jobs(self, printer: str) -> int:
        """Cancel all non-completed jobs for *printer*. Returns number cancelled."""
        if not CUPS_AVAILABLE:
            return 0
        try:
            conn = _cups_mod.Connection()
            jobs = conn.getJobs(which_jobs="not-completed", my_jobs=False)
            count = 0
            for job_id, attrs in jobs.items():
                if printer not in attrs.get("job-printer-uri", ""):
                    continue
                try:
                    conn.cancelJob(job_id)
                    count += 1
                except Exception:
                    pass
            log.info("Cancelled %d job(s) for printer %s", count, printer)
            return count
        except Exception as exc:
            log.warning("cancel_all_jobs error: %s", exc)
            return 0

    def build_config(self, printer: str, options: dict[str, str] | None = None) -> PrintConfig:
        opts = dict(options or {})
        opts = self._resolve_synthetic_options(printer, opts)
        return PrintConfig(printer_name=printer, options=opts)

    def _resolve_synthetic_options(
        self, printer: str, options: dict[str, str],
    ) -> dict[str, str]:
        """Translate UI-only synthetic option names (e.g. __BORDERLESS__) into
        the real CUPS options the printer driver expects, then strip them."""
        raw = options.pop(_BORDERLESS_SYNTH, "")
        if not raw:
            return options
        state = self._borderless_state.get(printer)
        if state is None:
            return options
        on = raw.lower() in ("true", "yes", "1", "on")
        if state["kind"] == "epij_psrc":
            options[_EPSON_PSRC_OPT] = (
                _EPSON_PSRC_BORDERLESS if on else _EPSON_PSRC_STANDARD
            )
        elif state["kind"] == "pagesize_variant" and on:
            size_opt = state["size_opt"]
            variant_map = state["variant_map"]
            # Use whichever PageSize-ish option the user actually picked,
            # falling back to size_opt if present.
            current_size = options.get(size_opt, "")
            if current_size in variant_map:
                options[size_opt] = variant_map[current_size]
        return options

    def borderless_state(self, printer: str) -> dict | None:
        """Read-only access to the synth borderless state cached for *printer*."""
        return self._borderless_state.get(printer)

    @classmethod
    def find_ppd_path(cls, printer: str) -> str | None:
        """Public accessor for the printer's PPD path (or None if missing)."""
        return cls._find_ppd_path(printer)

    @classmethod
    def get_page_size_points(cls, printer: str, *candidates: str) -> tuple[float, float] | None:
        """Return physical (w_pt, h_pt) for a PageSize choice on *printer*.

        Tries each *candidate* in order — typically the raw CUPS value first
        (e.g. ``"A4"`` for generic drivers, ``"1"`` for vendor-coded drivers),
        then the display label (``"A4"``) as a fallback. ``*PaperDimension``
        entries are keyed by display name in most vendor PPDs, so caller
        should pass both raw and display when available.
        """
        from workflow.page_geometry import get_page_size_points as _g
        ppd = cls._find_ppd_path(printer)
        for c in candidates:
            if c:
                dims = _g(ppd, c)
                if dims:
                    return dims
        return None

    @classmethod
    def get_imageable_area_points(
        cls, printer: str, *candidates: str,
    ) -> tuple[float, float] | None:
        """Return the printable (w_pt, h_pt) for a PageSize choice on *printer*,
        from the PPD's ``*ImageableArea`` entry.  Same candidate-ordering rules
        as :meth:`get_page_size_points`.  ``None`` if the PPD or entry is absent.
        """
        from workflow.page_geometry import get_imageable_area_points as _g
        ppd = cls._find_ppd_path(printer)
        for c in candidates:
            if c:
                dims = _g(ppd, c)
                if dims:
                    return dims
        return None
