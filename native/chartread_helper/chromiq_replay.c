/* Replay instrument for chromiq-chartread — a fake `inst` object that
 * feeds scripted readings through the REAL read_strips code path, so the
 * whole decision logic (recognition, warnings, autosave, F7-R) is
 * exercised without hardware.
 *
 * Replay script format (one directive per line, '#' comments):
 *   PATCHES <steps-per-pass>
 *   STRIP <pass-label>            begins a strip block
 *   <X> <Y> <Z>                   one patch reading (D50 XYZ, 0..100)
 *
 * All *faults* and *wrong swipes* are injected live via the JSON command
 * channel (see chromiq_json.c): {"cmd":"swipe"} triggers reading the armed
 * strip; optional fields "as":"<label>" (values of another strip),
 * "reversed":true, "fault":"misread|coms|needs_cal|wrong_config", and with
 * a misread "reason":"<the driver's sentence>" (B1, e.g. "Too many patches").
 * {"cmd":"switch"} presses the instrument's button (B1): a trigger while a
 * strip waits for one, otherwise an inst_event_switch, as the i1Pro's switch
 * thread reports it.
 * {"cmd":"presses","at_ms":"0,300,650"} is a person pressing it at those
 * times (button gestures, 2026-10-25): each press is a {"cmd":"switch"},
 * and a press that triggers a waiting STRIP is a quick tap, whose scan ends
 * "Reading is too short" 220 ms later (Basti's ColorMunki: 0.19-0.27 s).
 * CHROMIQ_REPLAY_INSTRUMENT=colormunki|dtp20 makes the fake instrument report
 * that model instead of an i1Pro (for the instrument gating tests).
 *
 * AGPL-3.0 — see ../instlib/License.txt. Part of ChromIQ issue #126. */

#ifdef SALONEINSTLIB
#include "sa_config.h"
#else
#include "aconfig.h"
#endif
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include "numsup.h"
#include "cgats.h"
#include "xspect.h"
#include "conv.h"
#include "insttypes.h"
#include "icoms.h"
#include "inst.h"

#include "chromiq_ext.h"
#include "chromiq_dualscan.h"
#ifdef NT
# include <windows.h>
# include <process.h>
#else
# include <pthread.h>
#endif

const char *cq_replay_path = NULL;

int cq_replay_active(void) {
	return cq_replay_path != NULL;
}

/* ---------------- script storage ---------------- */

#define CQ_MAX_STRIPS 512
#define CQ_MAX_STEPS  64

typedef struct {
	char   label[8];
	int    n;
	double xyz[CQ_MAX_STEPS][3];
	/* "X-Rite i1Pro 3: keep M0, M1 and M2" (Beta, 2026-11-15): the same
	 * patches under the conditions a COND block gives (0 M0, 1 M1, 2 M2) */
	int    cn[3];
	double cxyz[3][CQ_MAX_STEPS][3];
	/* The i1Pro 2 dual scan (step 1, 2026-11-18): per patch the lamp and
	 * the UV-LED reading as spectra (LAMP / UV lines), allocated on demand */
	int    dl, du;
	double (*dlamp)[CQ_DUAL_NB];
	double (*duv)[CQ_DUAL_NB];
} cq_strip;

static cq_strip cq_strips[CQ_MAX_STRIPS];
static int      cq_nstrips = 0;
static int      cq_stipa = 0;

static int cq_replay_conds = 0;	/* the script carries COND blocks */
/* The i1Pro 2 dual scan (step 1, 2026-11-18): the script's DUALCAL block
 * (W, T, E, KA, KD lines of 36 values, CLOCKS lamp uv) and whether any strip
 * carries LAMP / UV lines. SYNTHETIC data only in the repository. */
static cq_dual_cal cq_dcal;
static int cq_replay_dual = 0;		/* the script carries LAMP / UV lines */
static int cq_replay_dualcal = 0;	/* ... and a DUALCAL block */

static int cq_read36(const char *p, double *out) {
	int j, n = 0;
	for (j = 0; j < CQ_DUAL_NB; j++) {
		char *e;
		double v = strtod(p, &e);
		if (e == p)
			break;
		out[j] = v;
		p = e;
		n++;
	}
	return n;
}
/* The margin tolerance (Beta): the paper white of the fake sheet, for the
 * segments a refused swipe hands over ("PAPER X Y Z" in the script). */
static double cq_paper[3] = { 93.3, 96.6, 79.9 };

int cq_replay_load(const char *path) {
	FILE *fp;
	char line[2048];		/* a LAMP / UV line holds 36 values */
	cq_strip *cur = NULL;
	int cond = -1;			/* inside a COND block of the current strip */
	int indcal = 0;			/* inside the DUALCAL block */

	if ((fp = fopen(path, "r")) == NULL) {
		a1logw(g_log, "chromiq replay: can't open '%s'\n", path);
		return 1;
	}
	while (fgets(line, sizeof(line), fp) != NULL) {
		char lab[8];
		double x, y, z;
		if (line[0] == '#' || line[0] == '\n' || line[0] == '\r')
			continue;
		if (sscanf(line, "PATCHES %d", &cq_stipa) == 1)
			continue;
		if (sscanf(line, "PAPER %lf %lf %lf", &x, &y, &z) == 3) {
			cq_paper[0] = x; cq_paper[1] = y; cq_paper[2] = z;
			continue;
		}
		if (strncmp(line, "DUALCAL", 7) == 0) {
			memset(&cq_dcal, 0, sizeof(cq_dcal));
			cq_dcal.nb = CQ_DUAL_NB;
			cq_dcal.wl_short = 380.0;
			cq_dcal.wl_long = 730.0;
			cq_replay_dualcal = 1;
			indcal = 1;
			continue;
		}
		if (indcal) {
			double *dst = NULL;
			const char *rest = NULL;
			int lc, uc;
			if (strncmp(line, "W ", 2) == 0) { dst = cq_dcal.W; rest = line + 2; }
			else if (strncmp(line, "T ", 2) == 0) { dst = cq_dcal.T; rest = line + 2; cq_dcal.have_uv_tile = 1; }
			else if (strncmp(line, "E ", 2) == 0) { dst = cq_dcal.E; rest = line + 2; }
			else if (strncmp(line, "KA ", 3) == 0) { dst = cq_dcal.kA; rest = line + 3; }
			else if (strncmp(line, "KD ", 3) == 0) { dst = cq_dcal.kD; rest = line + 3; }
			else if (sscanf(line, "CLOCKS %d %d", &lc, &uc) == 2) {
				cq_dcal.cal_lamp_clocks = lc;
				cq_dcal.cal_uv_clocks = uc;
				continue;
			}
			if (dst != NULL) {
				cq_read36(rest, dst);	/* missing values stay 0 (KA/KD: 18) */
				continue;
			}
			indcal = 0;			/* anything else ends the block */
		}
		if (cur != NULL && (strncmp(line, "LAMP ", 5) == 0 || strncmp(line, "UV ", 3) == 0)) {
			int uv = line[0] == 'U';
			int *cnt = uv ? &cur->du : &cur->dl;
			double (**arr)[CQ_DUAL_NB] = uv ? &cur->duv : &cur->dlamp;
			if (*arr == NULL && (*arr = calloc(CQ_MAX_STEPS, sizeof(**arr))) == NULL) {
				fclose(fp);
				return 1;
			}
			if (*cnt < CQ_MAX_STEPS
			 && cq_read36(line + (uv ? 3 : 5), (*arr)[*cnt]) == CQ_DUAL_NB)
				(*cnt)++;
			cq_replay_dual = 1;
			continue;
		}
		if (sscanf(line, "STRIP %7s", lab) == 1) {
			if (cq_nstrips >= CQ_MAX_STRIPS) {
				fclose(fp);
				return 1;
			}
			cur = &cq_strips[cq_nstrips++];
			memset(cur, 0, sizeof(*cur));
			strncpy(cur->label, lab, sizeof(cur->label) - 1);
			cond = -1;
			continue;
		}
		{
			char cn[8];
			if (cur != NULL && sscanf(line, "COND %7s", cn) == 1) {
				cond = strcmp(cn, "M0") == 0 ? 0 : strcmp(cn, "M1") == 0 ? 1
				     : strcmp(cn, "M2") == 0 ? 2 : -1;
				if (cond >= 0)
					cq_replay_conds = 1;
				continue;
			}
		}
		if (cur != NULL && cond >= 0 && sscanf(line, "%lf %lf %lf", &x, &y, &z) == 3) {
			if (cur->cn[cond] < CQ_MAX_STEPS) {
				cur->cxyz[cond][cur->cn[cond]][0] = x;
				cur->cxyz[cond][cur->cn[cond]][1] = y;
				cur->cxyz[cond][cur->cn[cond]][2] = z;
				cur->cn[cond]++;
			}
			continue;
		}
		if (cur != NULL && sscanf(line, "%lf %lf %lf", &x, &y, &z) == 3
		 && cur->n < CQ_MAX_STEPS) {
			cur->xyz[cur->n][0] = x;
			cur->xyz[cur->n][1] = y;
			cur->xyz[cur->n][2] = z;
			cur->n++;
		}
	}
	fclose(fp);
	a1logd(g_log, 1, "chromiq replay: %d strips of %d patches from '%s'\n",
	       cq_nstrips, cq_stipa, path);
	return cq_nstrips == 0;
}

/* ---------------- the ruler check (Beta, 2026-11-14) ----------------
 * A fake ruler record per swipe, shaped like the drivers' (cq_ruler.h), so
 * the helper's event, the GUI and the diagnostics file can be exercised
 * without an instrument. The model follows the i1Pro 2 recordings: one
 * sample per clock, samples = readings x clocks - 5, quadrature codes.
 * Modes ("ruler" on a swipe): clean (a whole strip: 340 steps on an i1Pro 2,
 * 560 on an i1Pro 3), partial (about 40 % of it), fast, none (no ruler), garbled (an impossible jump),
 * short (half the samples), late (the stream did not end: the driver gives
 * the ruler up), failed (a USB error on the ruler channel). No "ruler": as
 * clean. */
#include "cq_ruler.h"
static char cq_rr_mode[16] = "";
static int cq_rr_pending = 0;
static int cq_rr_npatch = 0;
static int cq_rr_given_up = 0;		/* as the i1Pro 2 driver: for the session */
/* The margin tolerance (Beta, 2026-11-16): the segments the fake recogniser
 * cut for a refused swipe, in swipe order, and why it refused. */
#define CQ_RM_MAX (CQ_MAX_STEPS + 8)
static int cq_rm_n = 0, cq_rm_why = 0, cq_rm_noleader = 0;
static int cq_rm_nudge = 0;	/* "nudge": the first segment moves BACKWARDS */
static double cq_rm_xyz[CQ_RM_MAX][3];

int cq_replay_margin_ok(void) {
	return cq_replay_ruler_gen() == 2;
}

static void cq_rm_add(const double *xyz) {
	if (cq_rm_n < CQ_RM_MAX) {
		cq_rm_xyz[cq_rm_n][0] = xyz[0];
		cq_rm_xyz[cq_rm_n][1] = xyz[1];
		cq_rm_xyz[cq_rm_n][2] = xyz[2];
		cq_rm_n++;
	}
}

/* mode: "start" (the margin before the first patch counted), "end" (after
 * the last), "both", "noleader" (the recording began on the first patch),
 * "shifted" (began one patch in, the margin counted: a WRONG reading the
 * rules must refuse), "nudge" (set down on patch 2, pulled back over it to
 * the edge of patch 1, then swiped: patch 2 twice, the first time with the
 * ruler going backwards; review 2026-11-16, BLOCKER-1, a WRONG reading the
 * rules must refuse). xyz: the strip's patches in swipe order. */
static void cq_replay_margin_note(const char *mode, const char *reason,
                                  double (*xyz)[3], int n) {
	int i, st = 0;
	cq_rm_n = 0;
	cq_rm_nudge = strcmp(mode, "nudge") == 0;
	cq_rm_noleader = strcmp(mode, "noleader") == 0 || cq_rm_nudge;
	cq_rm_why = strcmp(reason, "Too many patches") == 0 ? 0x3C
	          : strcmp(reason, "Swipe didn't start and end on the media") == 0 ? 0x42
	          : 0x3B;
	if (!cq_rm_noleader)
		cq_rm_add(cq_paper);					/* the leader */
	if (strcmp(mode, "start") == 0 || strcmp(mode, "both") == 0
	 || strcmp(mode, "shifted") == 0)
		cq_rm_add(cq_paper);					/* the margin, as a patch */
	if (strcmp(mode, "shifted") == 0)
		st = 1;
	if (cq_rm_nudge && n > 1) {
		cq_rm_add(xyz[1]);						/* patch 2, backwards */
		st = 1;
	}
	for (i = st; i < n; i++)
		cq_rm_add(xyz[i]);
	if (strcmp(mode, "end") == 0 || strcmp(mode, "both") == 0)
		cq_rm_add(cq_paper);
	cq_rm_add(cq_paper);						/* the trailer */
}

int cq_replay_ruler_gen(void) {
	const char *ri = getenv("CHROMIQ_REPLAY_INSTRUMENT");
	if (ri != NULL && strcmp(ri, "i1pro2") == 0)
		return 2;
	if (ri != NULL && strcmp(ri, "i1pro3") == 0)
		return 3;
	return 0;
}

static void cq_replay_ruler_note(const char *mode, int npatch) {
	strncpy(cq_rr_mode, mode != NULL && mode[0] ? mode : "clean",
	        sizeof(cq_rr_mode) - 1);
	cq_rr_mode[sizeof(cq_rr_mode) - 1] = '\0';
	cq_rr_npatch = npatch;
	cq_rr_pending = 1;
}

int cq_replay_ruler_take(void *vout) {
	cq_ruler_rec *r = (cq_ruler_rec *)vout;
	static const unsigned char cyc[4] = { 0, 2, 3, 1 };
	int gen = cq_replay_ruler_gen(), readings, clocks, travel = 340, n, k;
	long total, i, a, b, pos = 0, last_at = -1;
	int last_code = -1;
	unsigned char *zeb;
	memset(r, 0, sizeof(*r));
	if (!cq_rr_pending || gen == 0 || cq_rr_given_up)
		return 0;
	cq_rr_pending = 0;
	clocks = gen == 2 ? 136 : 172;
	(void)k;
	readings = strcmp(cq_rr_mode, "fast") == 0 ? 220 : 600;
	total = (long)readings * clocks - (gen == 2 ? 5 : 0);
	if (gen == 3)
		travel = 560;		/* 0.5 mm per step: a 280 mm swipe */
	if (strcmp(cq_rr_mode, "partial") == 0)
		travel = gen == 3 ? 200 : 136;
	if (strcmp(cq_rr_mode, "short") == 0)
		total /= 2;
	r->valid = 1;
	r->gen = gen;
	r->readings = readings;
	r->clocks = clocks;
	r->clock_s = gen == 2 ? 36e-6 : 15.3e-6;
	r->inttime = clocks * r->clock_s;
	r->ended = gen == 2 ? CQ_RULER_END_SHORT : CQ_RULER_END_ARGYLL;
	r->argyll_used = gen == 3 && strcmp(cq_rr_mode, "none") != 0
	                 && strcmp(cq_rr_mode, "garbled") != 0;
	if (strcmp(cq_rr_mode, "failed") == 0) {
		r->ended = CQ_RULER_END_ERROR;
		r->icom_err = 0x100;
		r->giveup = gen == 2 ? CQ_RULER_GIVEUP_ERROR : 0;
		cq_rr_given_up = r->giveup;
		return 1;
	}
	if (strcmp(cq_rr_mode, "late") == 0) {
		r->ended = CQ_RULER_END_RUNNING;
		r->stream_did_not_end = 1;
		r->giveup = CQ_RULER_GIVEUP_NOTEND;
		cq_rr_given_up = r->giveup;
		return 1;
	}
	if ((zeb = (unsigned char *)malloc(total)) == NULL)
		return 1;
	/* the instrument rests on the lead-in for 10 %, then moves evenly */
	a = cq_rm_n > 0 && cq_rm_noleader ? 0 : total / 10;
	b = total - total / 10;
	for (i = 0; i < total; i++) {
		long step = i < a ? 0 : i >= b ? travel : (i - a) * travel / (b - a);
		if (cq_rm_n > 1 && cq_rm_nudge) {
			/* back over the first segment, then forwards to the end */
			long t1 = (long)(0.85 * readings / (cq_rm_n - 1)) * clocks;
			long back = travel / (cq_rm_n - 1);
			step = i < t1 ? -(i * back / t1)
			     : i >= b ? travel : -back + (i - t1) * (travel + back) / (b - t1);
		}
		zeb[i] = strcmp(cq_rr_mode, "none") == 0 ? 3 : cyc[(4 - (step & 3)) & 3];
		if (strcmp(cq_rr_mode, "garbled") == 0 && i == total / 2)
			zeb[i] = cyc[(4 - (step & 3) + 2) & 3];
	}
	cq_ruler_rec_feed(r, zeb, total, &pos, &last_at, &last_code);
	free(zeb);
	r->bytes = r->samples;
	/* today's cut: the patches evenly between 15 % and 85 % of the readings */
	n = cq_rr_npatch > 0 && cq_rr_npatch <= CQ_RULER_MAXPATCH ? cq_rr_npatch : 0;
	for (k = 0; k < n; k++) {
		int s0 = (int)(readings * (0.15 + 0.70 * k / n));
		int s1 = (int)(readings * (0.15 + 0.70 * (k + 1) / n));
		int len = s1 - s0, no = len * 2 / 3;
		cq_ruler_rec_cut(r, k, s0 + (len - no) / 2, no, 0);
	}
	/* a refused swipe: no cut, but the segments, evenly from the first
	 * reading (or 15 % in) to 85 %, the trailer to the end */
	if (cq_rm_n > 0 && gen == 2) {
		ipatch *v = (ipatch *)calloc(cq_rm_n, sizeof(ipatch));
		int inner = cq_rm_n - 1 - (cq_rm_noleader ? 0 : 1), j0 = cq_rm_noleader ? 0 : 1;
		r->ncut = 0;
		if (v != NULL && inner > 0) {
			double lo = cq_rm_noleader ? 0.0 : 0.15 * readings, hi = 0.85 * readings;
			for (k = 0; k < cq_rm_n; k++) {
				int s0, s1;
				if (k < j0) {
					s0 = 0; s1 = (int)lo;
				} else if (k == cq_rm_n - 1) {
					s0 = (int)hi; s1 = readings;
				} else {
					s0 = (int)(lo + (hi - lo) * (k - j0) / inner);
					s1 = (int)(lo + (hi - lo) * (k - j0 + 1) / inner);
				}
				r->cand_ss[k] = s0 + 1;
				r->cand_no[k] = s1 - s0 - 2;
				r->cand_flags[k] = 0;
				v[k].XYZ[0] = cq_rm_xyz[k][0];
				v[k].XYZ[1] = cq_rm_xyz[k][1];
				v[k].XYZ[2] = cq_rm_xyz[k][2];
				v[k].XYZ_v = 1;
				v[k].mtype = inst_mrt_reflective;
				v[k].sp.spec_n = 0;
			}
			r->cand_vals = v;
			r->ncand = cq_rm_n;
			r->cand_why = cq_rm_why;
		} else
			free(v);
	}
	cq_rm_n = 0;
	cq_rm_nudge = 0;
	return 1;
}

static cq_strip *cq_find(const char *label) {
	int i;
	for (i = 0; i < cq_nstrips; i++)
		if (strcmp(cq_strips[i].label, label) == 0)
			return &cq_strips[i];
	return NULL;
}

/* ---------------- fake inst object ---------------- */

typedef struct _cq_inst {
	INST_OBJ_BASE
} cq_inst;

/* Minimal icoms stand-in: read_strips touches it->icom only for
 * port_type()/port_attr() guards (serial baud fallback, fast-serial
 * checks) — report a plain USB port so those branches stay inert. */
static icom_type cq_icom_port_type(struct _icoms *p) {
	(void)p;
	return icomt_usb;
}

static icom_type cq_icom_port_attr(struct _icoms *p) {
	(void)p;
	return icomt_usb;
}

static icoms cq_fake_icom;	/* zero-init; only the two members below are set */

/* The instrument-shaped hang (tests only, 2026-10-25): what Basti's
 * ColorMunki did after quit, Ctrl+C or stdin closing. CHROMIQ_REPLAY_STUCK=
 * close: closing the instrument never returns (a switch thread that never
 * ends); =signal: Argyll's USB signal handler, installed when communications
 * open, never returns either (its port close blocks). The engine must end
 * anyway, within its exit grace. */
#ifndef NT
# include <signal.h>
# include <unistd.h>
static void cq_stuck_handler(int sig) {
	(void)sig;
	for (;;)
		pause();
}
#endif

static int cq_stuck(const char *what) {
	const char *e = getenv("CHROMIQ_REPLAY_STUCK");
	return e != NULL && strstr(e, what) != NULL;
}

static inst_code cq_init_coms(inst *p, baud_rate br, flow_control fc, double tout) {
	(void)br; (void)fc; (void)tout;
	p->gotcoms = 1;
#ifndef NT
	if (cq_stuck("signal")) {
		signal(SIGINT, cq_stuck_handler);
		signal(SIGTERM, cq_stuck_handler);
	}
#endif
	return inst_ok;
}

static inst_code cq_init_inst(inst *p) {
	p->inited = 1;
	return inst_ok;
}

static instType cq_get_itype(inst *p) {
	/* reads like an i1Pro strip reader, unless a test asked for another
	 * model (CHROMIQ_REPLAY_INSTRUMENT, see cq_new_replay_inst) */
	return p->dtype != instUnknown ? p->dtype : instI1Pro;
}

static char *cq_get_serial_no(inst *p) {
	(void)p;
	return "";
}

static inst_code cq_get_set_opt(inst *p, inst_opt_type m, ...) {
	(void)p;
	/* R4 (4.3.39): the filter the driver reads through, for the helper's
	 * "filter" event. CHROMIQ_REPLAY_FILTER=uvcut is an i1Pro with a
	 * physical UV-cut filter; =unset answers nothing; anything else none. */
	if (m == inst_stat_get_filter) {
		const char *f = getenv("CHROMIQ_REPLAY_FILTER");
		inst_opt_filter *filt;
		va_list args;
		va_start(args, m);
		filt = va_arg(args, inst_opt_filter *);
		va_end(args);
		if (f != NULL && strcmp(f, "unset") == 0)
			return inst_unsupported;
		*filt = (f != NULL && strcmp(f, "uvcut") == 0)
		        ? inst_opt_filter_UVCut : inst_opt_filter_none;
		return inst_ok;
	}
	return inst_ok;
}

/* Which read mode the fake instrument advertises (CHROMIQ_REPLAY_MODE):
 * 0 = strip+spot (default), 2 = xy (SpectroScan), 3 = chart (i1iSis). Lets
 * tests drive the fork into rmode 2/3 to exercise the XY/chart engine paths
 * and the mode-fallback gate. */
static int cq_replay_mode = 0;

static void cq_capabilities(inst *p, inst_mode *cap1,
	inst2_capability *cap2, inst3_capability *cap3) {
	(void)p;
	if (cap1 != NULL) {
		if (cq_replay_mode == 3)
			*cap1 = inst_mode_ref_chart | inst_mode_reflection | inst_mode_colorimeter;
		else if (cq_replay_mode == 2)
			*cap1 = inst_mode_ref_xy | inst_mode_reflection | inst_mode_colorimeter;
		else
			*cap1 = inst_mode_ref_strip | inst_mode_ref_spot | inst_mode_reflection
			      | inst_mode_colorimeter;
	}
	/* No xy_holdrel / xy_locate: the fake table needs no hold/clear/sight
	 * steps, so the XY loop skips straight to read_xy. */
	if (cap2 != NULL)
		*cap2 = inst2_user_trig | inst2_user_switch_trig | inst2_bidi_scan;
	if (cap3 != NULL)
		*cap3 = inst3_none;
}

static inst_code cq_meas_config(inst *p, inst_mode *mmodes,
	inst_cal_cond *cconds, int *conf_ix) {
	(void)p; (void)mmodes; (void)cconds; (void)conf_ix;
	return inst_unsupported;
}

static inst_code cq_check_mode(inst *p, inst_mode m) {
	(void)p;
	if (cq_replay_mode == 3)
		return IMODETST(m, inst_mode_ref_chart) ? inst_ok : inst_unsupported;
	if (cq_replay_mode == 2)
		return IMODETST(m, inst_mode_ref_xy) ? inst_ok : inst_unsupported;
	if (IMODETST(m, inst_mode_ref_strip) || IMODETST(m, inst_mode_ref_spot))
		return inst_ok;
	return inst_unsupported;
}

/* Fill a value array with a synthetic neutral reading — enough to exercise the
 * whole-chart / whole-sheet transfer + JSON events + autosave without hardware.
 * (Faithful colours would need the real motorized table; the protocol is what
 * these paths are tested for.) */
static void cq_fill_synthetic(ipatch *vals, int n) {
	int i;
	for (i = 0; i < n; i++) {
		memset(&vals[i], 0, sizeof(ipatch));
		vals[i].XYZ[0] = 50.0;
		vals[i].XYZ[1] = 50.0;
		vals[i].XYZ[2] = 50.0;
		vals[i].XYZ_v = 1;
		vals[i].mtype = inst_mrt_reflective;
		vals[i].sp.spec_n = 0;
	}
}

static inst_code cq_read_chart(inst *p, int npatch, int pich, int sip,
	int *pis, int chid, ipatch *vals) {
	(void)p; (void)pich; (void)sip; (void)pis; (void)chid;
	cq_fill_synthetic(vals, npatch);
	return inst_ok;
}

static inst_code cq_read_xy(inst *p, int pis, int sip, int npatch,
	char *pname, char *sname, double ox, double oy, double ax, double ay,
	double aax, double aay, double px, double py, ipatch *vals) {
	(void)p; (void)pis; (void)sip; (void)pname; (void)sname;
	(void)ox; (void)oy; (void)ax; (void)ay; (void)aax; (void)aay; (void)px; (void)py;
	cq_fill_synthetic(vals, npatch);
	return inst_ok;
}

static inst_code cq_set_mode(inst *p, inst_mode m) {
	(void)p; (void)m;
	return inst_ok;
}

/* Optional calibration simulation (CHROMIQ_REPLAY_NEEDCAL): lets tests
 * exercise the JSON calibration handshake the real ColorMunki triggers —
 * one inst_cal_setup round (user positions the sensor), then inst_ok. */
static int cq_needcal_armed = 0;
static int cq_cal_step = 0;

/* A calibration the USER asks for (CHROMIQ_REPLAY_CAL), tests only:
 *   setup_ok    one placement prompt, then success
 *   fail_once   one placement prompt, then a failure; the next request
 *               succeeds after its prompt
 *   fail        one placement prompt, then a failure, every time
 *   unavailable the instrument reports nothing to calibrate
 * Unset, the replay reports nothing available, as it always has. The
 * failure is inst_hardware_fail, which the interp below names, so the GUI
 * receives a real sentence for its window. */
#define CQ_CALMODE_NONE      0
#define CQ_CALMODE_SETUP_OK  1
#define CQ_CALMODE_FAIL_ONCE 2
#define CQ_CALMODE_FAIL      3
#define CQ_CALMODE_UNAVAIL   4
static int cq_calmode = CQ_CALMODE_NONE;
static int cq_req_step = 0;
static int cq_req_fails_left = 0;

static int cq_calmode_offers(void) {
	return cq_calmode == CQ_CALMODE_SETUP_OK || cq_calmode == CQ_CALMODE_FAIL_ONCE
	    || cq_calmode == CQ_CALMODE_FAIL;
}

static inst_cal_type cq_needs_calibration(inst *p) {
	(void)p;
	return cq_needcal_armed ? inst_calt_ref_white : inst_calt_none;
}

static inst_code cq_get_n_a_cals(inst *p, inst_cal_type *needed,
	inst_cal_type *available) {
	(void)p;
	if (needed != NULL)
		*needed = inst_calt_none;
	if (available != NULL)
		*available = cq_calmode_offers() ? inst_calt_ref_white : inst_calt_none;
	return inst_ok;
}

static inst_code cq_calibrate(inst *p, inst_cal_type *calt, inst_cal_cond *calc,
	inst_calc_id_type *idtype, char id[CALIDLEN]) {
	(void)p; (void)idtype; (void)id;
	/* The requested calibration (CHROMIQ_REPLAY_CAL). Recognised by the
	 * inst_calt_available a request starts with, then by its own step. */
	if (!cq_needcal_armed && calt != NULL
	 && (*calt == inst_calt_available || cq_req_step == 1)) {
		if (*calt == inst_calt_available) {
			if (!cq_calmode_offers()) {
				*calt = inst_calt_none;
				return inst_ok;			/* nothing to do, as a driver says */
			}
			*calt = inst_calt_ref_white;
			cq_req_step = 0;		/* a cancelled request starts over */
		}
		if (cq_req_step == 0) {
			cq_req_step = 1;
			if (calc != NULL)
				*calc = inst_calc_man_ref_white;
			return inst_cal_setup;
		}
		cq_req_step = 0;
		if (cq_calmode == CQ_CALMODE_FAIL)
			return inst_hardware_fail;
		if (cq_calmode == CQ_CALMODE_FAIL_ONCE && cq_req_fails_left > 0) {
			cq_req_fails_left--;
			return inst_hardware_fail;
		}
		*calt = inst_calt_none;
		return inst_ok;
	}
	if (cq_needcal_armed && cq_cal_step == 0) {
		/* First round: ask the user to set the sensor to the white tile. */
		cq_cal_step = 1;
		if (calc != NULL)
			*calc = inst_calc_man_ref_white;
		return inst_cal_setup;
	}
	/* Done — clear the armed flag so the read loop proceeds. */
	cq_needcal_armed = 0;
	cq_cal_step = 0;
	if (calt != NULL)
		*calt = inst_calt_none;
	return inst_ok;
}

static void cq_set_uicallback(inst *p,
	inst_code (*uicallback)(void *cntx, inst_ui_purp purp), void *cntx) {
	p->uicallback = uicallback;
	p->uic_cntx = cntx;
}

static void cq_set_event_callback(inst *p,
	void (*eventcallback)(void *cntx, inst_event_type event), void *cntx) {
	p->eventcallback = eventcallback;
	p->event_cntx = cntx;
}

static char *cq_inst_interp_error(inst *p, inst_code ec) {
	(void)p;
	switch (ec & inst_mask) {
		case inst_misread:      return "Measurement misread (replay)";
		case inst_coms_fail:    return "Communications failure (replay)";
		case inst_needs_cal:    return "Instrument needs calibration (replay)";
		case inst_wrong_config: return "Sensor in wrong position (replay)";
		case inst_hardware_fail: return "White calibration failed (replay)";
		default:                return "Replay instrument error";
	}
}

/* B1: the sentence the last scripted misread asked for ("reason"), so the
 * GUI sees the driver's own words, as it does with a real instrument. */
static char cq_last_reason[96] = "";

static char *cq_interp_error(inst *p, int ec) {
	(void)p;
	if ((ec & inst_mask) == inst_misread && cq_last_reason[0] != '\0')
		return cq_last_reason;
	return "replay";
}

/* B1: the instrument's button. The replay instance and whether its strip is
 * waiting for a trigger, which is when a real driver hides the press from
 * the event callback and counts it as the trigger instead. */
static inst *volatile cq_replay_inst = NULL;
static volatile int cq_replay_waiting = 0;

void cq_replay_switch_press(void) {
	inst *p = cq_replay_inst;
	if (!cq_replay_active() || p == NULL)
		return;
	if (cq_replay_waiting) {
		cq_trigger_ready_ms = 700;
		cq_trigger_pending = 1;
		return;
	}
	if (p->eventcallback != NULL)
		p->eventcallback(p->event_cntx, inst_event_switch);
}

/* Button gestures: the trigger now pending is a quick tap (a press from
 * {"cmd":"presses"}), so the scan it starts ends too short. */
static volatile int cq_replay_tap = 0;
#define CQ_TAP_MS 220

static void cq_replay_press_one(void) {
	if (cq_replay_waiting)
		cq_replay_tap = 1;
	cq_replay_switch_press();
}

typedef struct { int n; int at[16]; } cq_press_plan;

static void cq_press_plan_run(cq_press_plan *pl) {
	double t0 = cq_now_ms();
	int i;
	for (i = 0; i < pl->n; i++) {
		double due = t0 + pl->at[i];
		while (cq_now_ms() < due)
			msec_sleep(2);
		cq_replay_press_one();
	}
	free(pl);
}

#ifdef NT
static unsigned __stdcall cq_press_thread(void *a) {
	cq_press_plan_run((cq_press_plan *)a);
	return 0;
}
#else
static void *cq_press_thread(void *a) {
	cq_press_plan_run((cq_press_plan *)a);
	return NULL;
}
#endif

void cq_replay_presses(const char *at_ms) {
	cq_press_plan *pl;
	const char *q = at_ms;
	if (!cq_replay_active() || at_ms == NULL)
		return;
	if ((pl = (cq_press_plan *)calloc(1, sizeof(*pl))) == NULL)
		return;
	while (*q != '\0' && pl->n < 16) {
		char *e;
		long v = strtol(q, &e, 10);
		if (e == q)
			break;
		pl->at[pl->n++] = v < 0 ? 0 : (int)v;
		q = (*e == ',') ? e + 1 : e;
	}
#ifdef NT
	_beginthreadex(NULL, 0, cq_press_thread, pl, 0, NULL);
#else
	{
		pthread_t t;
		if (pthread_create(&t, NULL, cq_press_thread, pl) == 0)
			pthread_detach(t);
		else
			free(pl);
	}
#endif
}

static int cq_last_scomerr(inst *p) {
	(void)p;
	return 0;
}

static void cq_del(inst *p) {
	if (cq_stuck("close"))
		for (;;)
			msec_sleep(1000);
	if (p != NULL) {
		if (cq_replay_inst == p)
			cq_replay_inst = NULL;
		if (p->log != NULL)
			del_a1log(p->log);
		free(p);
	}
}

/* The heart: block until the ui-callback reports a key/trigger, or the
 * command thread posts a swipe; then either return the user event exactly
 * like a real driver, or fill vals[] from the replay script. */
/* ---------------- the conditions record (Beta, 2026-11-15) ----------------
 * As the i1Pro 3 driver's (i1pro3_cq_cond_take): for the swipe just made,
 * the same patches under the other conditions, from the script's COND
 * blocks, in the order the swipe gave them (a reversed swipe reverses them
 * too). Cleared at every reading, so a misread can never hand on an earlier
 * swipe's values. */
static ipatch cq_rc_vals[3][CQ_MAX_STEPS];
static int cq_rc_n = 0;
static int cq_rc_have[3] = { 0, 0, 0 };

int cq_replay_cond_ready(void) {
	const char *ri = getenv("CHROMIQ_REPLAY_INSTRUMENT");
	return cq_replay_conds && ri != NULL && strcmp(ri, "i1pro3") == 0;
}

static void cq_replay_cond_note(cq_strip *st, int npatch, int reversed) {
	int c, i;
	cq_rc_n = 0;
	for (c = 0; c < 3; c++) {
		cq_rc_have[c] = st != NULL && st->cn[c] >= npatch && npatch <= CQ_MAX_STEPS;
		for (i = 0; cq_rc_have[c] && i < npatch; i++) {
			int six = reversed ? npatch - 1 - i : i;
			memset(&cq_rc_vals[c][i], 0, sizeof(ipatch));
			cq_rc_vals[c][i].XYZ[0] = st->cxyz[c][six][0];
			cq_rc_vals[c][i].XYZ[1] = st->cxyz[c][six][1];
			cq_rc_vals[c][i].XYZ[2] = st->cxyz[c][six][2];
			cq_rc_vals[c][i].XYZ_v = 1;
			cq_rc_vals[c][i].mtype = inst_mrt_reflective;
			cq_rc_vals[c][i].mcond = c == 1 ? inst_mrc_D50 : c == 2 ? inst_mrc_uvcut
			                                                : inst_mrc_none;
		}
	}
	cq_rc_n = npatch;
}

int cq_replay_cond_take(int cond, void *outp, int n) {
	ipatch *out = (ipatch *)outp;
	if (cond < 0 || cond > 2 || n != cq_rc_n || n <= 0 || !cq_rc_have[cond])
		return 0;
	memcpy(out, cq_rc_vals[cond], sizeof(ipatch) * (size_t)n);
	return 1;
}

/* ---------------- the i1Pro 2 dual scan (step 1, 2026-11-18) ----------------
 * A strip with LAMP / UV lines is read as an i1Pro 2 dual scan would hand it
 * over: the main values are the LAMP spectra (as the driver's
 * i1pro_conv2XYZ makes them: percent reflectance, XYZ under D50, CIE 1931
 * 2 degree, x 100), and the raw record of this reading (lamp and UV
 * spectra per patch, 0..1, in the order the patches were filed, and the
 * script's DUALCAL) is what cq_replay_dual_take hands the helper, which
 * works out M1 and M2 itself (chromiq_dualscan.c). The UV pass arrives
 * already cut into patches here (the ruler cut is chromiq_dualscan.c's
 * cq_dual_cut, tested on its own). */
static int cq_rd_n = 0;
static double cq_rd_lamp[CQ_MAX_STEPS][CQ_DUAL_NB];
static double cq_rd_uv[CQ_MAX_STEPS][CQ_DUAL_NB];
static int cq_rd_have_uv = 0;

void cq_replay_spec_to_patch(const double *refl01, int nb, void *vp) {
	ipatch *v = (ipatch *)vp;
	xsp2cie *conv;
	int j;
	memset(v, 0, sizeof(*v));
	v->sp.spec_n = nb;
	v->sp.spec_wl_short = 380.0;
	v->sp.spec_wl_long = 730.0;
	v->sp.norm = 100.0;
	for (j = 0; j < nb; j++)
		v->sp.spec[j] = 100.0 * refl01[j];
	if ((conv = new_xsp2cie(icxIT_D50, 0.0, NULL, icxOT_CIE_1931_2, NULL,
	                        icSigXYZData, icxNoClamp)) != NULL) {
		conv->convert(conv, v->XYZ, &v->sp);
		conv->del(conv);
		for (j = 0; j < 3; j++)
			v->XYZ[j] *= 100.0;
		v->XYZ_v = 1;
	}
	v->mtype = inst_mrt_reflective;
	v->mcond = inst_mrc_none;
}

static inst_code cq_replay_dual_strip(cq_strip *st, int npatch, int reversed,
                                      ipatch *vals) {
	int i;
	for (i = 0; i < npatch; i++) {
		int six = reversed ? npatch - 1 - i : i;
		cq_replay_spec_to_patch(st->dlamp[six], CQ_DUAL_NB, &vals[i]);
		memcpy(cq_rd_lamp[i], st->dlamp[six], sizeof(cq_rd_lamp[i]));
		if (st->du >= npatch)
			memcpy(cq_rd_uv[i], st->duv[six], sizeof(cq_rd_uv[i]));
	}
	cq_rd_have_uv = st->du >= npatch;
	cq_rd_n = npatch;
	cq_rc_n = 0;			/* no i1Pro 3 conditions record */
	return inst_ok;
}

int cq_replay_dual_ready(void) {
	const char *ri = getenv("CHROMIQ_REPLAY_INSTRUMENT");
	return cq_replay_dual && ri != NULL && strcmp(ri, "i1pro2") == 0;
}

/* The last reading's raw record (n patches): 1 and the pointers, else 0.
 * *uv is NULL when the script gave no UV lines for it (the second pass is
 * missing); *cal is NULL when the script has no DUALCAL. */
int cq_replay_dual_take(int n, const cq_dual_cal **cal, const double **lamp,
                        const double **uv) {
	if (n <= 0 || n != cq_rd_n)
		return 0;
	*cal = cq_replay_dualcal ? &cq_dcal : NULL;
	*lamp = &cq_rd_lamp[0][0];
	*uv = cq_rd_have_uv ? &cq_rd_uv[0][0] : NULL;
	return 1;
}

static inst_code cq_read_strip(inst *p, char *name, int npatch, char *pname,
	int sguide, double pwid, double gwid, double twid, ipatch *vals) {
	cq_inst *cq = (cq_inst *)p;
	cq_strip *st;
	int i;

	(void)name; (void)sguide; (void)pwid; (void)gwid; (void)twid;

	cq_rc_n = 0;				/* the conditions record: this reading's only */
	cq_replay_waiting = 1;		/* B1: a press now is the trigger */
	for (;;) {
		/* Give the registered uicallback a chance — console keys and JSON
		 * nav commands surface here as inst_user_abort/inst_user_trig,
		 * exactly like a real driver polling during its wait. */
		if (cq->uicallback != NULL) {
			inst_code uev = cq->uicallback(cq->uic_cntx, inst_armed);
			if (uev == inst_user_abort) {
				cq_replay_waiting = 0;
				/* As the i1Pro and ColorMunki drivers do: their wait loop
				 * calls inst_triggered however it ended, a command included
				 * (i1pro_imp.c:3049, munki_imp.c:2132), then returns the
				 * abort. Modelled so a test sees what a real instrument
				 * makes of a goto at an armed strip (2026-10-23). */
				cq->uicallback(cq->uic_cntx, inst_triggered);
				return inst_user_abort;
			}
			/* inst_user_trig means "read now": treat as swipe of the
			 * armed strip with no overrides. */
			if (uev == inst_user_trig) {
				cq_swipe_as[0] = '\0';
				cq_swipe_reversed = 0;
				cq_swipe_fault[0] = '\0';
				cq_swipe_pending = 1;
			}
		}

		/* #202: {"cmd":"trigger"} is the instrument's button. Do what the
		 * i1Pro driver does on a press (i1pro_imp.c:3049, 3196-3203): report
		 * inst_triggered, then raise the ready-to-scan moment after the lamp
		 * delay -- through Argyll's own issue_scan_ready() when an event
		 * callback is registered, else the driver's own delayed beep. The
		 * strip is then read by the next {"cmd":"swipe"}, as before. */
		if (cq_trigger_pending) {
			int delay = cq_trigger_ready_ms;
			int tap = cq_replay_tap;
			cq_trigger_pending = 0;
			cq_replay_tap = 0;
			cq_replay_waiting = 0;	/* B1: from here a press is an event */
			if (cq->uicallback != NULL)
				cq->uicallback(cq->uic_cntx, inst_triggered);
			if (p->eventcallback != NULL)
				issue_scan_ready(p, delay);
			else
				msec_beep(delay, 1000, 200);
			if (tap) {
				/* A quick tap: the button is let go before the
				 * instrument has gathered its first readings. */
				msec_sleep(CQ_TAP_MS);
				strncpy(cq_last_reason, "Reading is too short",
				        sizeof(cq_last_reason) - 1);
				return inst_misread;
			}
		}

		if (cq_swipe_pending) {
			char fault[16];
			cq_swipe_pending = 0;
			cq_replay_ruler_note(cq_swipe_ruler, npatch);
			cq_replay_waiting = 0;
			strncpy(fault, cq_swipe_fault, sizeof(fault) - 1);
			fault[sizeof(fault) - 1] = '\0';
			cq_last_reason[0] = '\0';
			cq_rm_n = 0;		/* the margin tolerance: this swipe's segments only */
			cq_rm_nudge = 0;

			if (fault[0] != '\0') {
				strncpy(cq_last_reason, cq_swipe_reason, sizeof(cq_last_reason) - 1);
				cq_last_reason[sizeof(cq_last_reason) - 1] = '\0';
				if (cq_swipe_margin[0] != '\0' && strcmp(fault, "misread") == 0) {
					/* the margin tolerance (Beta): what the recogniser cut */
					cq_strip *ms = cq_find(cq_swipe_as[0] != '\0' ? cq_swipe_as : pname);
					if (ms != NULL && ms->n >= npatch) {
						double sw[CQ_MAX_STEPS][3];
						for (i = 0; i < npatch; i++) {
							int six = cq_swipe_reversed ? npatch - 1 - i : i;
							sw[i][0] = ms->xyz[six][0];
							sw[i][1] = ms->xyz[six][1];
							sw[i][2] = ms->xyz[six][2];
						}
						cq_replay_margin_note(cq_swipe_margin, cq_swipe_reason, sw, npatch);
					}
				}
				if (strcmp(fault, "misread") == 0)
					return inst_misread;
				if (strcmp(fault, "coms") == 0)
					return inst_coms_fail;
				if (strcmp(fault, "needs_cal") == 0)
					return inst_needs_cal;
				if (strcmp(fault, "wrong_config") == 0)
					return inst_wrong_config;
				return inst_misread;
			}

			st = cq_find(cq_swipe_as[0] != '\0' ? cq_swipe_as : pname);
			cq_rd_n = 0;		/* the dual record: this reading's only */
			if (st != NULL && st->dl >= npatch && npatch <= CQ_MAX_STEPS)
				return cq_replay_dual_strip(st, npatch, cq_swipe_reversed, vals);
			if (st == NULL || st->n < npatch)
				return inst_misread;	/* script gap reads as misread */

			for (i = 0; i < npatch; i++) {
				int six = cq_swipe_reversed ? npatch - 1 - i : i;
				memset(&vals[i], 0, sizeof(ipatch));
				vals[i].XYZ[0] = st->xyz[six][0];
				vals[i].XYZ[1] = st->xyz[six][1];
				vals[i].XYZ[2] = st->xyz[six][2];
				vals[i].XYZ_v = 1;
				vals[i].mtype = inst_mrt_reflective;
				vals[i].sp.spec_n = 0;
			}
			cq_replay_cond_note(st, npatch, cq_swipe_reversed);
			return inst_ok;
		}

		msec_sleep(20);
	}
}

/* ---------------- spot (patch-by-patch) reading ----------------
 * The spot loop arms the current patch's expected XYZ before each read
 * (cq_replay_arm_spot); the fake instrument echoes it back, so the whole
 * patch-by-patch path runs headless with measured == expected. A pending
 * fault (set via {"cmd":"swipe","fault":"…"}) is honoured once, exactly
 * like the strip path, so misread/coms/needs-cal recovery is testable. */
static double cq_spot_armed[3] = {0.0, 0.0, 0.0};

void cq_replay_arm_spot(const double xyz[3]) {
	cq_spot_armed[0] = xyz[0];
	cq_spot_armed[1] = xyz[1];
	cq_spot_armed[2] = xyz[2];
}

/* ---------------- the spot session (item 43, 2026-11-24) ----------------
 * --spot-session has no chart: press n reads the script's patches one after
 * the other (STRIP A's first, second, ..., then B's, round again after the
 * last). The main value is the patch's XYZ line, or its LAMP spectrum when
 * the script has one (an i1Pro 2 dual script); the conditions record of the
 * press holds its COND values (an i1Pro 3 script), the dual record its LAMP
 * and UV spectra. Only the spot session arms this; the chart's patch loop
 * arms the expected value (cq_replay_arm_spot), as before. */
static int cq_spot_n_armed = 0;
static int cq_spot_n_strip = 0, cq_spot_n_patch = 0;

static int cq_spot_n_count(const cq_strip *st) {
	return st->n > st->dl ? st->n : st->dl;
}

void cq_replay_arm_spot_n(int n) {
	int total = 0, s, k;
	for (s = 0; s < cq_nstrips; s++)
		total += cq_spot_n_count(&cq_strips[s]);
	cq_spot_n_armed = 0;
	if (total <= 0 || n < 0)
		return;
	k = n % total;
	for (s = 0; s < cq_nstrips; s++) {
		int c = cq_spot_n_count(&cq_strips[s]);
		if (k < c)
			break;
		k -= c;
	}
	cq_spot_n_strip = s;
	cq_spot_n_patch = k;
	cq_spot_n_armed = 1;
}

/* the armed patch into val and the press's records (one value) */
static void cq_replay_spot_n_fill(ipatch *val) {
	cq_strip *st = &cq_strips[cq_spot_n_strip];
	int i = cq_spot_n_patch, c;
	memset(val, 0, sizeof(ipatch));
	cq_rc_n = 0;
	cq_rd_n = 0;
	if (st->dl > i)
		cq_replay_spec_to_patch(st->dlamp[i], CQ_DUAL_NB, val);
	else if (st->n > i) {
		val->XYZ[0] = st->xyz[i][0];
		val->XYZ[1] = st->xyz[i][1];
		val->XYZ[2] = st->xyz[i][2];
		val->XYZ_v = 1;
		val->mtype = inst_mrt_reflective;
	}
	for (c = 0; c < 3; c++) {
		cq_rc_have[c] = st->cn[c] > i;
		if (!cq_rc_have[c])
			continue;
		memset(&cq_rc_vals[c][0], 0, sizeof(ipatch));
		cq_rc_vals[c][0].XYZ[0] = st->cxyz[c][i][0];
		cq_rc_vals[c][0].XYZ[1] = st->cxyz[c][i][1];
		cq_rc_vals[c][0].XYZ[2] = st->cxyz[c][i][2];
		cq_rc_vals[c][0].XYZ_v = 1;
		cq_rc_vals[c][0].mtype = inst_mrt_reflective;
		cq_rc_vals[c][0].mcond = c == 1 ? inst_mrc_D50 : c == 2 ? inst_mrc_uvcut
		                                               : inst_mrc_none;
	}
	cq_rc_n = 1;
	if (st->dl > i) {
		memcpy(cq_rd_lamp[0], st->dlamp[i], sizeof(cq_rd_lamp[0]));
		cq_rd_have_uv = st->du > i;
		if (cq_rd_have_uv)
			memcpy(cq_rd_uv[0], st->duv[i], sizeof(cq_rd_uv[0]));
		cq_rd_n = 1;
	}
}

static inst_code cq_read_sample(inst *p, char *name, ipatch *val,
	instClamping clamp) {
	cq_inst *cq = (cq_inst *)p;
	(void)name; (void)clamp;

	/* The instrument's button reads the patch, as on a ColorMunki or an
	 * i1Pro, whose spot wait triggers on the switch exactly as their strip
	 * wait does (munki_imp.c:2101-2133). Modelled so a test can press the
	 * button patch by patch ({"cmd":"switch"}) as a person would (agent 33,
	 * 2026-10-23); before, a press here was only reported. */
	cq_rc_n = 0;		/* no conditions record for a patch in a replay */
	cq_replay_waiting = 1;
	for (;;) {
		int pressed = 0;
		if (cq_trigger_pending) {
			cq_trigger_pending = 0;
			cq_replay_tap = 0;	/* a spot reading takes no slide */
			pressed = 1;
		}
		/* Same poll as cq_read_strip: nav/goto commands surface as
		 * inst_user_abort, the read trigger as inst_user_trig. */
		if (cq->uicallback != NULL) {
			inst_code uev = pressed ? inst_user_trig
			                        : cq->uicallback(cq->uic_cntx, inst_armed);
			if (uev == inst_user_abort) {
				cq_replay_waiting = 0;
				return inst_user_abort;
			}
			if (pressed)
				cq->uicallback(cq->uic_cntx, inst_triggered);
			if (uev == inst_user_trig) {
				char fault[16];
				cq_replay_waiting = 0;
				strncpy(fault, cq_swipe_fault, sizeof(fault) - 1);
				fault[sizeof(fault) - 1] = '\0';
				cq_swipe_fault[0] = '\0';
				cq_swipe_pending = 0;
				if (fault[0] != '\0') {
					if (strcmp(fault, "misread") == 0)
						return inst_misread;
					if (strcmp(fault, "coms") == 0)
						return inst_coms_fail;
					if (strcmp(fault, "needs_cal") == 0)
						return inst_needs_cal;
					/* Knut's real case 1 (#131, 2026-07-28): the head
					 * left in the calibration position. It is NOT a
					 * misread — it falls into chartread's "unexpected
					 * error" branch, which prints a different message
					 * and is the one Skip Patch has to survive. */
					if (strcmp(fault, "wrong_config") == 0)
						return inst_wrong_config;
					return inst_misread;
				}
				if (cq_spot_n_armed) {	/* the spot session (item 43) */
					cq_spot_n_armed = 0;
					cq_replay_spot_n_fill(val);
					return inst_ok;
				}
				memset(val, 0, sizeof(ipatch));
				val->XYZ[0] = cq_spot_armed[0];
				val->XYZ[1] = cq_spot_armed[1];
				val->XYZ[2] = cq_spot_armed[2];
				val->XYZ_v = 1;
				val->mtype = inst_mrt_reflective;
				val->sp.spec_n = 0;
				return inst_ok;
			}
		}
		msec_sleep(20);
	}
}

/* Members read_strips touches but never exercises on the strip path. */
static inst_code cq_unsupported(void) {
	return inst_unsupported;
}

inst *cq_new_replay_inst(a1log *log,
	inst_code (*uicallback)(void *cntx, inst_ui_purp purp), void *cntx) {
	cq_inst *p;

	if ((p = (cq_inst *)calloc(1, sizeof(cq_inst))) == NULL)
		return NULL;

	/* Arm the calibration simulation from the environment (tests only). */
	cq_needcal_armed = (getenv("CHROMIQ_REPLAY_NEEDCAL") != NULL);
	cq_cal_step = 0;

	/* The requested-calibration simulation (tests only). */
	{
		const char *cm = getenv("CHROMIQ_REPLAY_CAL");
		cq_calmode = CQ_CALMODE_NONE;
		cq_req_step = 0;
		cq_req_fails_left = 0;
		if (cm != NULL) {
			if (strcmp(cm, "setup_ok") == 0)
				cq_calmode = CQ_CALMODE_SETUP_OK;
			else if (strcmp(cm, "fail_once") == 0) {
				cq_calmode = CQ_CALMODE_FAIL_ONCE;
				cq_req_fails_left = 1;
			} else if (strcmp(cm, "fail") == 0)
				cq_calmode = CQ_CALMODE_FAIL;
			else if (strcmp(cm, "unavailable") == 0)
				cq_calmode = CQ_CALMODE_UNAVAIL;
		}
	}

	/* Which read mode to advertise (tests only): xy / chart / default. */
	{
		const char *rm = getenv("CHROMIQ_REPLAY_MODE");
		cq_replay_mode = 0;
		if (rm != NULL) {
			if (strcmp(rm, "chart") == 0)
				cq_replay_mode = 3;
			else if (strcmp(rm, "xy") == 0)
				cq_replay_mode = 2;
		}
	}

	p->log = new_a1log_d(log);
	p->init_coms          = cq_init_coms;
	p->init_inst          = cq_init_inst;
	p->get_itype          = cq_get_itype;
	p->get_serial_no      = cq_get_serial_no;
	p->get_set_opt        = cq_get_set_opt;
	p->capabilities       = cq_capabilities;
	p->meas_config        = cq_meas_config;
	p->check_mode         = cq_check_mode;
	p->set_mode           = cq_set_mode;
	p->needs_calibration  = cq_needs_calibration;
	p->get_n_a_cals       = cq_get_n_a_cals;
	p->calibrate          = cq_calibrate;
	p->set_uicallback     = cq_set_uicallback;
	p->set_event_callback = cq_set_event_callback;
	p->inst_interp_error  = cq_inst_interp_error;
	p->interp_error       = cq_interp_error;
	p->read_strip         = cq_read_strip;
	p->read_sample        = cq_read_sample;
	p->read_chart         = cq_read_chart;
	p->read_xy            = cq_read_xy;
	p->last_scomerr       = cq_last_scomerr;
	p->del                = cq_del;
	p->dtype              = instI1Pro;
	{
		/* Button gestures: which model the fake instrument is (tests only).
		 * The gate (cq_button_retry_ok) asks the model, as with real ones. */
		const char *ri = getenv("CHROMIQ_REPLAY_INSTRUMENT");
		if (ri != NULL && strcmp(ri, "colormunki") == 0)
			p->dtype = instColorMunki;
		else if (ri != NULL && strcmp(ri, "dtp20") == 0)
			p->dtype = instDTP20;
		else if (ri != NULL && strcmp(ri, "i1pro2") == 0)
			p->dtype = instI1Pro2;	/* the ruler check (Beta) */
		else if (ri != NULL && strcmp(ri, "i1pro3") == 0)
			p->dtype = instI1Pro3;
	}
	cq_fake_icom.port_type = cq_icom_port_type;
	cq_fake_icom.port_attr = cq_icom_port_attr;
	p->icom               = &cq_fake_icom;
	p->uicallback         = uicallback;
	p->uic_cntx           = cntx;

	cq_replay_inst = (inst *)p;
	return (inst *)p;
}
