"""Engine-off, argument level: ProfileBuilder._build_args for every control
state of the Build tab (each field alone at every offered value, plus combos),
printed as JSON. Run once per tree; the two outputs must be identical."""
import dataclasses, json, sys
from pathlib import Path
tree = Path(sys.argv[1]); sys.path.insert(0, str(tree))
from workflow.profile_builder import ProfileBuilder, ProfileParams
ti3 = Path(sys.argv[2])
VALUES = {
 "description": ["", "Prüfdruck Müller"], "algorithm": ["l", "x"], "quality": list("lmhu"),
 "b2a_quality": ["", *"lmhun"], "smoothing": [0.25, 0.5, 1.0, 2.0, 4.0],
 "dark_emphasis": [1.0, 2.0, 3.5, 4.0], "gamut_src": ["", "/Applications/Argyll/ref/ClayRGB1998.icm"],
 "gamut_sat_src": ["", "/Applications/Argyll/ref/sRGB.icm"], "manufacturer": ["", "ACME"],
 "model": ["", "M9"], "copyright": ["", "© 2026 Müller"], "no_input_shaper": [False, True],
 "no_output_shaper": [False, True], "illuminant": ["", "A", "C", "D50", "D50M2", "D65", "D65M2", "F5", "F8", "F10"],
 "observer": ["", "1931_2", "1964_10", "2015_2", "2015_10"], "fwa_enabled": [False, True],
 "fwa_illum": ["", "D50", "A", "D50M2", "D65M2"], "src_viewing_cond": ["", "mt", "md", "pe", "pp", "pc"],
 "dst_viewing_cond": ["", "mt", "md", "pe", "pp", "pc"], "z_surface": ["", "m"], "z_media_type": ["", "t"],
 "z_polarity": ["", "n"], "z_color_mode": ["", "b"], "z_default_intent": ["", "p", "r", "s", "a"],
 "no_perc_gamut": [False, True], "no_sat_gamut": [False, True], "inv_gamut_map": [False, True],
 "perc_intent": ["", "p", "r", "s", "la", "lp", "pa", "ms", "a", "aa", "aw", "al"],
 "sat_intent": ["", "s", "ms", "r", "pa"], "no_grid_pos": [False, True], "no_embedded_data": [False, True],
 "k_rule": ["", *"zhxrp"], "k_locus": [False, True], "k_stle": [0.0, 0.2], "k_stpo": [0.1, 0.3],
 "k_enpo": [0.9, 0.7], "k_enle": [1.0, 0.8], "k_shape": [1.0, 1.5],
 "spectral_physics": [False, True], "icc_version": ["2", "4", "both"], "noise_model": [False, True],
 "render_style": ["argyll", "bijective"],
}
pb = ProfileBuilder.__new__(ProfileBuilder)
base = ProfileParams(ti3_path=ti3, verbose=True, gamut_sat_src="/Applications/Argyll/ref/ClayRGB1998.icm")
out = {}
for f, vals in VALUES.items():
    for v in vals:
        p = dataclasses.replace(base, **{f: v})
        out[f"{f}={v!r}"] = pb._build_args(p)
for combo in ({"k_rule": "p", "k_locus": True, "k_stle": 0.2}, {"fwa_enabled": True, "fwa_illum": "D50M2"},
              {"z_surface": "m", "z_default_intent": "p", "z_color_mode": "b"},
              {"perc_intent": "pa", "sat_intent": "ms", "src_viewing_cond": "mt", "dst_viewing_cond": "pp",
               "no_perc_gamut": True, "inv_gamut_map": True}):
    out[json.dumps(combo, sort_keys=True)] = pb._build_args(dataclasses.replace(base, **combo))
print(json.dumps(out, indent=0, ensure_ascii=False))
