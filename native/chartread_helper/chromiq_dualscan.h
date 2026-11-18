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
 * "uv_pass_misaligned": the alignment gate, cut.py::_flatness). */
const char *cq_dual_cut(int nb, int ncell, const int (*cells)[2],
                        int nlamp, const double *lamp_pos,
                        int nuv, const double *uv_pos, const double *uv,
                        double trim, int min_readings,
                        double *out, int *counts);

#define CQ_DUAL_TRIM 0.2
#define CQ_DUAL_MIN_UV 3
/* review 2026-11-18 (S2 / S3), the same numbers as model.py / cut.py */
#define CQ_DUAL_MIN_TILE_TE 100.0	/* the UV LED lit: Te 380-410 nm, emission units */
#define CQ_DUAL_TILE_LO 380.0
#define CQ_DUAL_TILE_HI 410.0
#define CQ_DUAL_MAX_FLATNESS 0.01	/* an aligned UV pass */
#define CQ_DUAL_MIN_ALIGN_SPREAD 0.05	/* the cells differ enough to judge */

/* The alignment measure (cut.py::_flatness): NAN when not judged. */
double cq_dual_flatness(int nb, int ncell, const int (*cells)[2],
                        const double *lamp_pos, int nuv, const double *uv_pos,
                        const double *uv, double trim);

#endif /* CHROMIQ_DUALSCAN_H */
