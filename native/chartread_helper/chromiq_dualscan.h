/* CHROMIQ_EXT: the X-Rite i1Pro 2 dual scan (step 1, 2026-11-18): M0, M1 and
 * M2 of a patch from its lamp reading and its UV-LED reading. Pure arithmetic,
 * no instrument access: the C twin of workflow/dual_scan/model.py and
 * workflow/dual_scan/cut.py (tests/test_i1pro2_dual_scan_engine.py holds the
 * two to the same numbers). The formula and its derivation are in model.py.
 *
 *   Ue = U * EMIS        Te = (T / W) * EMIS
 *   J  = s kA (Ue - Te L) / (1 - s kA Te)
 *   M2 = L - J           M1 = L + (kD / kA - 1) J      (J = 0 where kA = 0)
 *
 * AGPL-3.0 - see ../instlib/License.txt. */
#ifndef CHROMIQ_DUALSCAN_H
#define CHROMIQ_DUALSCAN_H

#define CQ_DUAL_NB 36			/* the i1Pro 2's standard bands, 380-730 nm */

/* What one calibration and the instrument's tables give (lamp-white units). */
typedef struct {
	int nb;
	double wl_short, wl_long;
	double W[CQ_DUAL_NB];		/* the tile read with the lamp */
	double T[CQ_DUAL_NB];		/* the tile read with the UV LED */
	double E[CQ_DUAL_NB];		/* reflectance -> emission factor */
	double kA[CQ_DUAL_NB];		/* EEPROM 0x2f77, zero outside 410-550 nm */
	double kD[CQ_DUAL_NB];		/* EEPROM 0x2f76 */
	int have_uv_tile;			/* the calibration read the tile with the UV LED */
	int cal_lamp_clocks, cal_uv_clocks;	/* 0 = not known */
} cq_dual_cal;

/* Reason ids (the same words as workflow/dual_scan/reasons.py). */
#define CQ_DUAL_OK					NULL

/* Check the calibration and tables: NULL when usable, else a reason id. */
const char *cq_dual_check(const cq_dual_cal *c);

/* M1 and M2 (0..1 reflectance) of one patch from L and U (0..1, lamp-white
 * units) with scale s. NULL on success, else a reason id. */
const char *cq_dual_patch(const cq_dual_cal *c, double s, const double *L,
                          const double *U, double *m1, double *m2);

/* The UV pass cut into the lamp cells by ruler position (cut.py): cells
 * [ncell] = {first lamp reading, count}; lamp_pos[nlamp], uv_pos[nuv],
 * uv[nuv][nb]; out[ncell][nb], counts[ncell]. NULL on success, else a
 * reason id ("no_ruler", "uv_pass_count", "uv_pass_short",
 * "uv_pass_stalled", "uv_pass_too_fast": cut.py::travel_verdict;
 * "uv_pass_misaligned": the alignment gate, cut.py::_flatness;
 * "uv_pass_shifted": the same over the averaging window).
 * A patch's UV readings are those whose ruler position lies in its lamp
 * cell's span (the first to the last lamp reading's position) less *edge*
 * ruler steps at each end (CQ_DUAL_EDGE_STEPS, cut.py EDGE_STEPS); *trim*
 * is the alignment gate's own window (a fraction of the span at each end,
 * CQ_DUAL_TRIM), unchanged since 4.3.45. */
const char *cq_dual_cut(int nb, int ncell, const int (*cells)[2],
                        int nlamp, const double *lamp_pos,
                        int nuv, const double *uv_pos, const double *uv,
                        double trim, int min_readings, double edge,
                        double *out, int *counts);

/* THE UV READINGS OF A PATCH (after 4.3.54; second fix round of 2026-11-21).
 * The cells are ArgyllCMS's own, already trimmed to the clean middle 66 % of
 * each patch it found in the lamp pass (its i1Pro driver, "Trim to 66 %"), and
 * it accepts a lamp patch from 4 readings there. Until 4.3.54 the UV pass then
 * used only the central 60 % of that span, so it needed about 1.5 times slower
 * movement than the lamp pass. Now the UV positions are first corrected by
 * the offset measured per strip (cq_dual_align, below), and a patch's UV
 * readings are those in the whole span less CQ_DUAL_EDGE_STEPS at each end.
 * The PHYSICAL reason for a quarter step: what is left after the correction
 * is the offset estimate's own scatter, at most 0.20 steps on instrument 1's
 * 13 recorded strips replayed at up to 1.5 times the speed and with up to 5
 * times the noise (median 0.05), rounded up to the next quarter step; the
 * readings beyond the span stay inside ArgyllCMS's own trimmed-off sixth of
 * the patch. PER PATCH, replayed with the UV positions shifted -6 to +6
 * steps by 0.25, at 1, 1.1, 1.25 and 1.5 times the speed: on every strip
 * lined up and accepted, every patch within 0.09 dE00 (M2) and 0.02 (M1) of the same
 * patch read at the recorded alignment with 4.3.54's window; no good pass
 * refused (2 to 5 times the noise); the first refusal for speed at about 1.7
 * times the recorded pace (median; 4.3.54 1.05, the lamp pass about 1.67).
 * The narrow window is used ONLY on lined-up positions (chromiq_dualdev.c
 * cq_dd_edge); a strip that is not lined up gets 4.3.54's central 60 % and
 * 4.3.54's limits (design section 17). Work folder
 * 2026-11-21_uv_pass_build, proof3/. */
#define CQ_DUAL_EDGE_STEPS 0.25
#define CQ_DUAL_TRIM 0.2			/* the alignment gate's window only */
#define CQ_DUAL_MIN_UV 3			/* a noise floor: 3 readings of 4.9 ms */
/* review 2026-11-18 (S2 / S3), the same numbers as model.py / cut.py */
#define CQ_DUAL_MIN_TILE_TE 100.0	/* the UV LED lit: Te 380-410 nm, emission units */
#define CQ_DUAL_TILE_LO 380.0
#define CQ_DUAL_TILE_HI 410.0
#define CQ_DUAL_MAX_FLATNESS 0.01	/* an aligned UV pass */
/* THE PASSES LINED UP WHERE THEY ARE AVERAGED (fix round of 2026-11-21,
 * review B1). The gate above looks at the central 60 % of each span, but the
 * readings are averaged out to half a step from its ends, so a misalignment
 * of 1 to 4 steps changed the averaged readings (M2 up to 2.7 dE00) while
 * that gate saw clean readings. So the same measure is also taken over the
 * averaging window ("uv_pass_shifted"). 0.001: replaying instrument 1's 13
 * recorded strips with their UV positions shifted by -3 to +3 steps, the
 * largest threshold that keeps every shift's worst accepted patch within
 * 0.1 dE00 of the unshifted level (0.47 -> at most 0.52 dE00), while the
 * passes as recorded give at most 0.00008, and simulated up to 1.75 times
 * faster at most 0.00027 (0 of 13 refused by it). */
#define CQ_DUAL_MAX_EDGE_FLATNESS 0.001
#define CQ_DUAL_MIN_ALIGN_SPREAD 0.05	/* the cells differ enough to judge */

/* The alignment measure (cut.py::_flatness): NAN when not judged. */
double cq_dual_flatness(int nb, int ncell, const int (*cells)[2],
                        const double *lamp_pos, int nuv, const double *uv_pos,
                        const double *uv, double trim);
/* The same measure over the AVERAGING window (the span less *edge* steps):
 * cut.py::_flatness(..., edge=). NAN when not judged. */
double cq_dual_window_flatness(int nb, int ncell, const int (*cells)[2],
                               const double *lamp_pos, int nuv, const double *uv_pos,
                               const double *uv, double edge);

/* DOES THIS UV PASS BELONG TO THIS LAMP PASS? (safety review 2026-11-18,
 * M1): the C twin of workflow/dual_scan/pairing.py::check_pairing, the same
 * rule and the same numbers (tests/test_i1pro2_dual_scan_pairing_c.py holds
 * the two together). At 380-400 nm nothing glows, so the UV reading there
 * is only the LED light the patch reflects, (T / W) x L of the SAME strip.
 * L[n][nb] the lamp pass's patches, U[n][nb] the UV pass cut into them, both
 * in lamp-white units. NULL = accepted (ev->checked 0 when the strip is too
 * dark to judge: the note pairing_not_checked), else "uv_pass_wrong_strip",
 * "uv_pass_no_uv_light", "bad_values" or the calibration's reason. */
#define CQ_DUAL_PAIR_LO 380.0				/* pairing.LED_BANDS_NM */
#define CQ_DUAL_PAIR_HI 400.0
#define CQ_DUAL_PAIR_MIN_CORRELATION 0.95	/* pairing.MIN_CORRELATION */
#define CQ_DUAL_PAIR_MAX_RATIO_ERROR 0.10	/* pairing.MAX_MEDIAN_RATIO_ERROR */
#define CQ_DUAL_PAIR_MIN_SPREAD 0.05		/* pairing.MIN_SPREAD */
#define CQ_DUAL_PAIR_LEVEL_FLOOR 0.05		/* pairing.LEVEL_FLOOR */
#define CQ_DUAL_PAIR_MIN_USABLE 2			/* pairing.MIN_USABLE */
#define CQ_DUAL_PAIR_MIN_FOR_CORRELATION 3	/* pairing.MIN_FOR_CORRELATION */
#define CQ_DUAL_PAIR_MIN_LIGHT_RATIO 0.3	/* pairing.MIN_LIGHT_RATIO */

typedef struct {
	double correlation;			/* NAN when not asked */
	double median_ratio_error;	/* NAN when not checked */
	int patches;
	int usable;					/* patches above the signal floor */
	int checked;				/* 0: too dark to judge (accepted, note pairing_not_checked) */
} cq_dual_pairing_ev;

const char *cq_dual_pairing(const cq_dual_cal *c, int n, const double *L, const double *U,
                            cq_dual_pairing_ev *ev);

/* LINING THE UV PASS UP WITH THE LAMP PASS (second fix round of 2026-11-21,
 * the verification's V1). The UV pass's ruler positions are off the lamp
 * pass's by an offset that differs per strip: the count labels one stripe
 * edge one count apart in the two directions, and the hand adds to that
 * (instrument 1's 13 recorded strips: -1.0 to +1.45 steps). A fixed edge
 * margin cannot cover it without giving the speed gain back, and a measure
 * averaged over the strip let a few damaged patch ends through. So the
 * offset is MEASURED per strip: at 380-400 nm nothing glows, so the UV pass's
 * reading there is (T / W) x the lamp reflectance at the same place; the
 * offset is the shift (-CQ_DUAL_ALIGN_SPAN .. +SPAN in CQ_DUAL_ALIGN_STEP)
 * that best lines the UV pass's 380-400 nm signal up with the lamp pass's own
 * readings there (least squares with one gain; the residual relative to the
 * UV signal's mean), over the strip's patches. The UV positions are then
 * corrected by it before the cut. Refused ("uv_pass_shifted") when the
 * offset is larger than CQ_DUAL_MAX_OFFSET (the instrument moved between
 * the passes beyond anything recorded). Not lined up (cut uncorrected with
 * 4.3.54's window, see CQ_DUAL_NOT_LINED_UP) when the fit is not clearly best
 * there (the residual 1 step either side less than CQ_DUAL_MIN_RISE times
 * the best: no clear patch edges to line up by: CQ_DUAL_NOT_LINED_UP, not a
 * refusal, see below). cut.py::estimate_offset is
 * the Python twin. lamp_pos[nlamp] / lamp_sig[nlamp]: each lamp reading's
 * position and its (T / W)-weighted 380-400 nm mean; uv_pos[nuv] /
 * uv_sig[nuv]: the same for the UV pass; [lo, hi]: the positions the strip's
 * patches span (first to last cell). NULL = lined up (*offset to subtract
 * from the UV positions, *rise the sharpness), else a reason id. */
#define CQ_DUAL_ALIGN_SPAN 6.5
#define CQ_DUAL_ALIGN_STEP 0.05
#define CQ_DUAL_ALIGN_MIN_READINGS 20
#define CQ_DUAL_MAX_OFFSET 3.0
#define CQ_DUAL_MIN_RISE 1.15
/* returned when there is nothing clear to line up by (patches alike at 380-400
 * nm, or too few readings): NOT a refusal. The caller then cuts that strip
 * uncorrected with 4.3.54's window (the central 60 %, edge < 0 to cq_dual_cut),
 * which the replay showed to hold up to about 2 steps of offset; the log says
 * "not_lined_up". cut.py NOT_LINED_UP. */
#define CQ_DUAL_NOT_LINED_UP "not_lined_up"
const char *cq_dual_align(int nlamp, const double *lamp_pos, const double *lamp_sig,
                          int nuv, const double *uv_pos, const double *uv_sig,
                          double lo, double hi, double *offset, double *rise);

/* Ruler positions of a hand dual strip's two passes (step 2): see
 * chromiq_dualscan.c. lp[n1], up[n2]; 1 = ok. */
#define CQ_DUAL_MAXCHG 20000
int cq_dual_positions(int first, int nch, const int *gaps, const unsigned char *codes,
                      long total, int n1, int n2, int clk, double *lp, double *up);

#endif /* CHROMIQ_DUALSCAN_H */
