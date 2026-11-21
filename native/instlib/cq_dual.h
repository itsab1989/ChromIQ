/* CHROMIQ FILE (not ArgyllCMS; scripts/vendor_instlib.py never writes it).
 * The X-Rite i1Pro 2 dual scan (2026-11-18, step 2): the API between
 * ChromIQ's helper and the driver code in cq_i1pro2_dual.h (included at the
 * end of i1pro_imp.c). Off (the helper not started with --dual-scale on a
 * real i1Pro 2) nothing here is ever called and no Argyll code path changes.
 *
 * WHAT IT SENDS TO THE INSTRUMENT (nothing that ArgyllCMS's own i1Pro 2 code
 * or X-Rite i1Profiler's recorded dual sessions do not send; see
 * docs/design/i1pro2_dual_scan.md section 7 and the safety brief):
 *   * measurement triggers (request 0xD4) with the UV-LED flag, the same
 *     request ArgyllCMS's own UV mode (inst_mode_ref_uv, i1p2_UV) sends, in
 *     the two recorded forms only: 0x0200 (the white tile; the UV half of a
 *     spot) and 0x0209 (the hand UV pass: scan + ruler end), always with a
 *     FIXED 41 lamp clocks as i1Profiler sent on every recorded UV-LED
 *     trigger (ArgyllCMS's lamp time would give 102 in scan mode, 51 in spot
 *     mode), at the integration the mode's own white calibration chose. Any
 *     other UV-LED form is refused before it is sent (an error, nothing on
 *     the wire): 0x0201, a UV scan without "ruler end", cannot go out;
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
#define CQ_DUAL_MAX_UV_READINGS 4000	/* a UV pass longer than this (about 20 s) is refused whole */
#define CQ_DUAL_UV_LAMPCLOCKS 41		/* every recorded UV-LED trigger (i1Profiler, two instruments) */
#define CQ_DUAL_FORM_UV_TILE 0x0200		/* UV LED, no scan: the tile, a spot's UV half */
#define CQ_DUAL_FORM_UV_PASS 0x0209		/* UV LED + scan + ruler end: the hand UV pass */

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
	int nread;				/* readings the pass gave, also when refused (too long) */
} cq_dual_uv;

/* The lamp reading's patch spectra BEFORE ArgyllCMS's output conversion
 * (XRGA, filter), so M1 / M2 go through the same conversion as M0. */
typedef struct {
	int n;
	double *L;				/* [n][36], malloc'd by the driver, owned by the caller after take */
	int clamp;				/* the measure call's clamp, for the same conversion */
} cq_dual_lamp;

/* When the steps of the last hand strip happened (after 4.3.54, the pace in
 * the app log): msec_time() stamps, 0 = not seen. Read only; nothing here
 * is sent to the instrument. clock_s: one integration clock in seconds (a
 * reading lasts clocks x clock_s). */
typedef struct {
	unsigned int lamp_trigger;	/* the lamp pass's trigger ("ruler start") */
	unsigned int lamp_done;		/* its readings were in */
	unsigned int lamp_off;		/* ArgyllCMS's last lamp on -> off */
	unsigned int uv_dark;		/* the last dark trigger before the UV pass */
	unsigned int uv_trigger;	/* the UV pass's trigger ("ruler end") */
	unsigned int uv_done;		/* its readings were in */
	double clock_s;
} cq_dual_times;
void i1pro2_cq_dual_times(void *pp, cq_dual_times *out);

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
int i1pro2_cq_dual_uv_pass_ready(void *pp);	/* 1 = the UV pass may be asked for (ruler stream of a lamp pass runs) */

/* The i1iO 2 table (2026-11-18, cq_i1pro2_dual.h section (d)): only the
 * helper's table-scan mode with --i1io-table-dual and the patch-by-patch
 * reading with --dual-table call these. cq_tscan_rec is cq_tscan.h's. */
#define CQ_TDUAL_PASS_LAMP 1
#define CQ_TDUAL_PASS_UV 2
/* the most readings a dual row of the table may ask for (5.8 s of UV light);
 * recorded UV-LED passes reach 1820 readings by hand, ChromIQ's rows need 550-590 */
#define CQ_TDUAL_NMAX 1150
int i1pro2_cq_tdual_on(void *pp, double *kA, double *kD);	/* CQ_DUAL_NA_*; no ruler */
int i1pro2_cq_dual_tile_save(void *pp, const cq_dual_tile *t);	/* 1 = kept */
int i1pro2_cq_dual_tile_restore(void *pp, cq_dual_tile *out);	/* 1 = of this white */
int i1pro2_cq_tdual_ready(void *pp, int pass, int nread, int have_tile, int *wait_ms,
                          char *why, int whylen);
void i1pro2_cq_tdual_disarm(void);	/* a calibration: no armed pass, no lamp pass done */
#ifdef CQ_TSCAN_H
int i1pro2_cq_tdual_fire(void *pp, int pass, int nread, int npatch, cq_tscan_rec *r,
                         int *volts_before, int *volts_after);
#endif
extern const char *i1pro2_cq_dual_tile_path_for_test;

#endif /* CQ_DUAL_H */
