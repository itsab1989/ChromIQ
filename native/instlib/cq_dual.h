/* CHROMIQ FILE (not ArgyllCMS; scripts/vendor_instlib.py never writes it).
 * The X-Rite i1Pro 2 dual scan (2026-11-18, step 2): the API between
 * ChromIQ's helper and the driver code in cq_i1pro2_dual.h (included at the
 * end of i1pro_imp.c). Off (the helper not started with --dual-scale on a
 * real i1Pro 2) nothing here is ever called and no Argyll code path changes.
 *
 * WHAT IT SENDS TO THE INSTRUMENT (nothing that ArgyllCMS's own i1Pro 2 code
 * or X-Rite i1Profiler's recorded dual sessions do not send; see
 * docs/design/i1pro2_dual_scan.md section 7 and the safety brief):
 *   * measurement triggers (request 0xD4) with the UV-LED flag 0x0200, the
 *     same request ArgyllCMS's own UV mode (inst_mode_ref_uv, i1p2_UV) sends,
 *     with the lamp pre-delay the lamp readings use (i1Profiler: 41 clocks
 *     for both), at the integration the mode's own white calibration chose;
 *   * dark triggers (flags 0x0000) as ArgyllCMS sends before every reading;
 *   * the UV LED's voltage query (request 0xD8, ArgyllCMS's
 *     i1pro2_getUVvolts), read only;
 *   * the ruler flags split over the two passes of a hand strip: the lamp
 *     pass with "ruler start" (0x0105), the UV pass with "ruler end"
 *     (0x0209), exactly as recorded (the ruler check Beta sends both on one
 *     scan, 0x010D).
 * NEVER: an EEPROM write (ENABLE_WRITE stays undefined), i1Profiler's own
 * indicator-light programs, any request not listed above.
 *
 * AGPL-3.0 like the rest of ChromIQ's helper code (see License.txt). */
#ifndef CQ_DUAL_H
#define CQ_DUAL_H

#define CQ_DUAL_BANDS 36			/* the i1Pro 2's standard bands, 380-730 nm */
#define CQ_DUAL_TABLE_N 18			/* kA / kD: 380-550 nm */
#define CQ_DUAL_TILE_DARK 10		/* i1Profiler's dual calibration: 10 dark ... */
#define CQ_DUAL_TILE_UV 5			/* ... and 5 UV-LED readings of the tile */
#define CQ_DUAL_MAX_UV_READINGS 4000	/* a UV pass longer than this is cut short */

/* Why the dual scan is not available (i1pro2_cq_dual_options). */
#define CQ_DUAL_NA_OK          0
#define CQ_DUAL_NA_INSTRUMENT  1	/* not an inited i1Pro 2 */
#define CQ_DUAL_NA_NO_UV_LED   2	/* the EEPROM reports no UV LED */
#define CQ_DUAL_NA_NO_TABLES   3	/* keys 0x2f77 / 0x2f76 missing or not 18 values */
#define CQ_DUAL_NA_HIGHRES     4	/* high resolution mode: the tables are 10 nm only */

/* The dual calibration's result, standard resolution, lamp-white units:
 * W the tile read with the lamp, T the tile read with the UV LED, E the
 * reflectance -> emission factor (emis_coef / white calibration factor). */
typedef struct {
	int ok;					/* 1 = T was read */
	double W[CQ_DUAL_BANDS];
	double T[CQ_DUAL_BANDS];
	double E[CQ_DUAL_BANDS];
	int lamp_clocks;		/* the white calibration's integration */
	int uv_clocks;			/* the UV tile reading's integration (= lamp_clocks) */
	int volts_before, volts_after;	/* 0xD8, -1 = not read */
	int mode_scan;			/* 1 = calibrated for scans, 0 = for spot readings */
} cq_dual_tile;

/* The last UV reading kept per reading (a UV pass) or per patch (a spot):
 * U[n][36] in lamp-white units (abswav x the lamp's calibration factor). */
typedef struct {
	int n;
	double *U;				/* malloc'd by the driver, owned by the caller after take */
	int clocks;
	int volts_before, volts_after;
	int uv_triggers;		/* UV-LED triggers this reading sent (1 expected) */
} cq_dual_uv;

/* The lamp reading's patch spectra BEFORE ArgyllCMS's output conversion
 * (XRGA, filter), so M1 / M2 go through the same conversion as M0. */
typedef struct {
	int n;
	double *L;				/* [n][36], malloc'd by the driver, owned by the caller after take */
	int clamp;				/* the measure call's clamp, for the same conversion */
} cq_dual_lamp;

/* Phases of one hand strip (i1pro2_cq_dual_arm). */
#define CQ_DUAL_PHASE_OFF   0
#define CQ_DUAL_PHASE_LAMP  1	/* the lamp pass: ruler START, keep L */
#define CQ_DUAL_PHASE_UV    3	/* the UV pass: the UV LED, ruler END, keep U per reading */
#define CQ_DUAL_PHASE_SPOT  4	/* a spot lamp reading: keep L */

int i1pro2_cq_dual_options(void *pp, int on, double *kA, double *kD);	/* CQ_DUAL_NA_* */
int i1pro2_cq_dual_tile(void *pp, cq_dual_tile *out);	/* I1PRO_OK or an error */
void i1pro2_cq_dual_arm(void *pp, int phase);
int i1pro2_cq_dual_phase(void *pp);
int i1pro2_cq_dual_spot_uv(void *pp, cq_dual_uv *out);	/* the UV half of a dual spot */
int i1pro2_cq_dual_take_uv(void *pp, cq_dual_uv *out);	/* the last UV pass, per reading */
int i1pro2_cq_dual_take_lamp(void *pp, cq_dual_lamp *out);
int i1pro2_cq_dual_conv(void *pp, void *vals, int n, const double *spec, int clamp);	/* ipatch *vals */
int i1pro2_cq_dual_uv_lit(void *pp);	/* 1 while a UV-LED trigger may be running */
int i1pro2_cq_dual_lamp_count(void *pp);	/* readings of the last lamp pass (its ruler share) */

#endif /* CQ_DUAL_H */
