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

/* THE UV READINGS OF A PATCH (after 4.3.54, 2026-11-21). The cells are ArgyllCMS's
 * own, already trimmed to the clean middle 66 % of each patch it found in the
 * lamp pass (its i1Pro driver, "Trim to 66 %"), and it accepts a lamp patch from
 * 4 readings there. Until 4.3.54 the UV pass then used only the central 60 %
 * of that span (trim 0.2 at each end), so it needed about 1.5 times slower
 * movement than the lamp pass (27 of 87 UV passes refused on a tester's
 * instrument, 21 Nov 2026). Now the whole span less half a ruler step at
 * each end. The PHYSICAL reason for the half step: the ruler's count labels
 * the same stripe edge one count apart in the two directions (it changes to
 * k + 1 on the way up and to k on the way down at the same edge), so the
 * UV pass's positions sit about one step off the lamp pass's (measured on
 * instrument 1's 13 recorded hand dual strips: 0.55 to 1.45 steps, median
 * 0.85); the span itself lies half a lamp reading inside the lamp readings'
 * own extent, so only the last half step at the leading end shows the
 * neighbour (UV readings there lean 0.7 % towards the neighbouring patch,
 * 1.7 % when the pass is 1.5 times faster; further in 0.1 %; including
 * them raised M2's mean by 0.002 to 0.003 dE00 and its worst patch to
 * 0.73 dE00 at twice the speed). Half a step keeps M2 at 4.3.54's level at
 * every speed replayed. Work folder 2026-11-21_uv_pass_build, proof.txt. */
#define CQ_DUAL_EDGE_STEPS 0.5
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

/* Ruler positions of a hand dual strip's two passes (step 2): see
 * chromiq_dualscan.c. lp[n1], up[n2]; 1 = ok. */
#define CQ_DUAL_MAXCHG 20000
int cq_dual_positions(int first, int nch, const int *gaps, const unsigned char *codes,
                      long total, int n1, int n2, int clk, double *lp, double *up);

#endif /* CHROMIQ_DUALSCAN_H */
