/* CHROMIQ_EXT: the X-Rite i1Pro 2 dual scan, the helper's side of the
 * instrument part (2026-11-18, step 2). Included ONCE by chromiq_chartread.c
 * (it uses that file's conditions record and event functions); the driver's
 * side is native/instlib/cq_i1pro2_dual.h, its API cq_dual.h.
 *
 * Nothing here runs unless a session was started with --dual-scale and
 * --condition-dir on a REAL i1Pro 2 that can do it (cq_dd_start); a replay
 * keeps the step-1 path (chromiq_replay.c).
 *
 * (a) After every successful calibration the tile is read with the UV LED
 *     at the calibration's own integration (cq_dd_after_cal); the result is
 *     checked by the arithmetic's own rules (chromiq_dualscan.c: tables, the
 *     UV LED lit) and reported as one event.
 * (b) A spot reading: the lamp reading as always, then the UV half on the
 *     same patch (one unit: either failing = the patch again).
 * (c) A hand strip: the lamp pass (ruler start) as always, then the helper
 *     asks for the UV pass itself (event dual_pass) and reads it (ruler
 *     end), each pass with its own verdict. The UV pass is asked for only
 *     when the lamp pass counted readings in a ruler stream that still runs
 *     (i1pro2_cq_dual_uv_pass_ready); otherwise its trigger could not carry
 *     "ruler end" (0x0201, never recorded), so M1 / M2 end for the session
 *     and M0 goes on (safety review 2026-11-18, M2). The UV pass is cut into
 *     the lamp pass's patches by the ruler (cq_dual_cut, with the travel and
 *     alignment gates) and must then be proved to belong to the strip
 *     (cq_dual_pairing, the twin of workflow/dual_scan/pairing.py; safety
 *     review M1: a pass over the neighbouring row passes every ruler gate).
 *     A UV pass longer than CQ_DUAL_MAX_UV_READINGS is refused whole (S3).
 *     A pass that fails makes the strip a misread: both passes are read
 *     again (on the instrument a UV pass can only be lined up with the lamp
 *     pass of the same ruler stream: the recorded wire has no other form;
 *     provisional for the first Beta, docs/design/i1pro2_dual_scan.md).
 * M1 / M2 go through the driver's own output conversion, exactly as M0.
 *
 * AGPL-3.0 - see ../instlib/License.txt. */

int i1pro2_cq_ruler_take(void *pp, void *vout);	/* the ruler check's record (cq_ruler.h) */

static struct {
	int on;					/* a real i1Pro 2 dual session */
	inst *it;
	cq_dual_cal cal;		/* kA / kD from the EEPROM; W / T / E from the last tile reading */
	int cal_ok;				/* the last calibration gave a usable dual calibration */
	int cal_scan;			/* ... made for scans (1) or spot readings (0) */
	const char *cal_why;	/* why not (a reason id of workflow/dual_scan/reasons.py) */
	int n;					/* patches of the last reading with M1 / M2 */
	cq_cx3 *vx;
	int vx_cap;
	const char *why;		/* why the last reading has none */
	/* 4.3.49: a strip the last calibration cannot give M1 / M2 for is read
	 * as a plain lamp scan (uncal: why, set by the strip loop) and refused
	 * ONCE per calibration with "calibrate again"; read again without a new
	 * calibration it is kept as M0 and M1 / M2 end (the way out) */
	const char *uncal;
	int cal_asked;
} cq_dd;

/* in cq_cond_for_session: NULL when this real i1Pro 2 can do it, else why */
static const char *cq_dd_start(inst *it) {
	int na, j;
	memset(&cq_dd.cal, 0, sizeof(cq_dd.cal));
	cq_dd.on = 0;
	cq_dd.cal_ok = 0;
	cq_dd.cal_why = "no_dual_calibration";
	cq_dd.uncal = NULL;
	cq_dd.cal_asked = 0;
	na = i1pro2_cq_dual_options(it, 1, cq_dd.cal.kA, cq_dd.cal.kD);
	switch (na) {
	case CQ_DUAL_NA_OK: break;
	case CQ_DUAL_NA_NO_UV_LED:
	case CQ_DUAL_NA_NO_TABLES: return "dual_no_uv_tables";
	case CQ_DUAL_NA_HIGHRES: return "dual_high_resolution";
	default: return "dual_not_available";
	}
	cq_dd.cal.nb = CQ_DUAL_NB;
	cq_dd.cal.wl_short = 380.0;
	cq_dd.cal.wl_long = 730.0;
	for (j = 0; j < CQ_DUAL_NB; j++)
		cq_dd.cal.W[j] = cq_dd.cal.E[j] = 1.0;	/* until a dual calibration */
	cq_dd.it = it;
	cq_dd.on = 1;
	/* THE i1iO 2 TABLE (--dual-table, 2026-11-18): every row is read by a
	 * reader of its own under -N, with the white ArgyllCMS restored; the
	 * dual tile kept for exactly that white is taken up again (it reads
	 * nothing). The hand path never passes --dual-table: unchanged. */
	if (cq_dual_table && cq_dd_nocal) {
		cq_dual_tile t;
		const char *why, *rwhy, *rdet = NULL;
		char rdet_esc[200];
		if (i1pro2_cq_dual_tile_restore(it, &t)) {
			for (j = 0; j < CQ_DUAL_NB; j++) {
				cq_dd.cal.W[j] = t.W[j];
				cq_dd.cal.T[j] = t.T[j];
				cq_dd.cal.E[j] = t.E[j];
			}
			cq_dd.cal.have_uv_tile = 1;
			cq_dd.cal.cal_lamp_clocks = t.lamp_clocks;
			cq_dd.cal.cal_uv_clocks = t.uv_clocks;
			cq_dd.cal_scan = t.mode_scan;
			why = cq_dual_check(&cq_dd.cal);
			cq_dd.cal_ok = why == NULL;
			cq_dd.cal_why = why != NULL ? why : "";
		}
		/* the same event as after a calibration (volts -1: nothing was read);
		 * 2026-11-24: plus why a kept tile was not taken up (reporting only) */
		rwhy = i1pro2_cq_dual_tile_restore_why(&rdet);
		cq_json_escape(rdet_esc, sizeof(rdet_esc), rdet != NULL ? rdet : "");
		cq_emit_raw("{\"event\":\"dual_calibration\",\"ok\":%s,\"why\":\"%s\",\"mode\":\"%s\","
		            "\"lamp_clocks\":%d,\"uv_clocks\":%d,\"volts\":[-1,-1],\"driver\":0,"
		            "\"restore\":\"%s\",\"restore_detail\":\"%s\"}",
		            cq_dd.cal_ok ? "true" : "false",
		            cq_dd.cal_ok ? "" : (cq_dd.cal.have_uv_tile ? cq_dd.cal_why : "no_dual_calibration"),
		            cq_dd.cal_scan ? "scan" : "spot", cq_dd.cal.cal_lamp_clocks,
		            cq_dd.cal.cal_uv_clocks, rwhy != NULL ? rwhy : "", rdet_esc);
	}
	return NULL;
}

/* (a) the dual calibration: right after every successful calibration */
static void cq_dd_after_cal(inst *p) {
	cq_dual_tile t;
	const char *why = NULL;
	int ev, j;
	if (!cq_dd.on || p != cq_dd.it)
		return;
	cq_dd.cal_ok = 0;
	cq_dd.cal.have_uv_tile = 0;
	cq_dd.cal_asked = 0;		/* a new calibration: asked again if it cannot count either */
	ev = i1pro2_cq_dual_tile(p, &t);
	if (ev != 0 || !t.ok)
		why = "no_dual_calibration";
	else {
		for (j = 0; j < CQ_DUAL_NB; j++) {
			cq_dd.cal.W[j] = t.W[j];
			cq_dd.cal.T[j] = t.T[j];
			cq_dd.cal.E[j] = t.E[j];
		}
		cq_dd.cal.have_uv_tile = 1;
		cq_dd.cal.cal_lamp_clocks = t.lamp_clocks;
		cq_dd.cal.cal_uv_clocks = t.uv_clocks;
		cq_dd.cal_scan = t.mode_scan;
		why = cq_dual_check(&cq_dd.cal);		/* the tables, the UV LED lit (uv_tile_dark) */
	}
	cq_dd.cal_ok = why == NULL;
	cq_dd.cal_why = why != NULL ? why : "";
	if (cq_dual_table && cq_dd.cal_ok)	/* the i1iO 2 table: kept for its rows' readers */
		(void)i1pro2_cq_dual_tile_save(p, &t);
	cq_emit_raw("{\"event\":\"dual_calibration\",\"ok\":%s,\"why\":\"%s\",\"mode\":\"%s\","
	            "\"lamp_clocks\":%d,\"uv_clocks\":%d,\"volts\":[%d,%d],\"driver\":%d}",
	            cq_dd.cal_ok ? "true" : "false", why != NULL ? why : "",
	            t.mode_scan ? "scan" : "spot", t.lamp_clocks, t.uv_clocks,
	            t.volts_before, t.volts_after, ev);
}

/* A failure of the PASS (read it again) rather than of the session (the
 * calibration, the ruler sensor, the arithmetic's inputs: M1 / M2 end for
 * the session, M0 goes on). */
static int cq_dd_pass_level(const char *why) {
	static const char *pass[] = { "lamp", "uv_pass_missing", "uv_pass_short",
	                              "uv_pass_stalled", "uv_pass_too_fast",
	                              "uv_pass_misaligned", "uv_pass_shifted", "uv_pass_count", "no_ruler",
	                              "uv_pass_wrong_strip", "uv_pass_no_uv_light",
	                              "uv_pass_too_long", "uv_spot_failed", NULL };
	int i;
	for (i = 0; why != NULL && pass[i] != NULL; i++)
		if (strcmp(why, pass[i]) == 0)
			return 1;
	return 0;
}

static void cq_dd_cal_hook(void *it) {
	cq_dd_after_cal((inst *)it);
}

/* M1 / M2 of n patches into cq_dd.vx, through the driver's conversion */
static const char *cq_dd_compute(const double *L, const double *U, int n, int clamp) {
	ipatch tmp;
	double m1[CQ_DUAL_NB], m2[CQ_DUAL_NB];
	int i;
	if (n > cq_dd.vx_cap) {
		free(cq_dd.vx);
		if ((cq_dd.vx = (cq_cx3 *)calloc((size_t)n, sizeof(cq_cx3))) == NULL) {
			cq_dd.vx_cap = 0;
			return "memory";
		}
		cq_dd.vx_cap = n;
	}
	memset(cq_dd.vx, 0, sizeof(cq_cx3) * (size_t)n);
	for (i = 0; i < n; i++) {
		const char *r = cq_dual_patch(&cq_dd.cal, cq_dual_scale, L + i * CQ_DUAL_NB,
		                              U + i * CQ_DUAL_NB, m1, m2);
		if (r != NULL)
			return r;
		memset(&tmp, 0, sizeof(tmp));
		if (i1pro2_cq_dual_conv(cq_dd.it, &tmp, 1, m1, clamp) != 0
		 || !cq_cx_from_ipatch(&cq_dd.vx[i][1], &tmp))
			return "conversion";
		memset(&tmp, 0, sizeof(tmp));
		if (i1pro2_cq_dual_conv(cq_dd.it, &tmp, 1, m2, clamp) != 0
		 || !cq_cx_from_ipatch(&cq_dd.vx[i][2], &tmp))
			return "conversion";
	}
	cq_dd.n = n;
	return NULL;
}

/* The calibration fits a reading of this mode at these clocks
 * (workflow/dual_scan/storage.calibration_fits, in C). */
static const char *cq_dd_fits(int scan, int clocks) {
	if (!cq_dd.cal.have_uv_tile)
		return "no_dual_calibration";
	if (!cq_dd.cal_ok)
		return cq_dd.cal_why[0] ? cq_dd.cal_why : "no_dual_calibration";
	if (scan != cq_dd.cal_scan)
		return "calibration_mode_changed";
	if (clocks > 0 && cq_dd.cal.cal_uv_clocks > 0 && clocks != cq_dd.cal.cal_uv_clocks)
		return "calibration_mismatch";
	return NULL;
}

/* The window a strip is cut with (third round of 2026-11-21, S1): the
 * narrow one (the span less CQ_DUAL_EDGE_STEPS) ONLY on positions that were
 * lined up; every other way here (nothing clear to line up by, no lamp
 * readings to line up with) gets 4.3.54's central 60 % (edge < 0). */
static double cq_dd_edge(const char *align_state) {
	return align_state != NULL && strcmp(align_state, "lined_up") == 0 ? CQ_DUAL_EDGE_STEPS : -1.0;
}

/* THE PACE OF A HAND DUAL STRIP (after 4.3.54): what the person needs to
 * learn his pace and what the app log keeps for a tester's report. Every
 * number is measured: readings x their integration time (the instrument
 * reads back to back while the button is held), the ruler's travel in
 * COUNTS (its mm scale is not measured for the i1Pro 2, so no mm/s), the
 * readings per patch of both passes, and when the steps happened. */
typedef struct {
	int have;
	int n1, n2, clocks;			/* readings of the lamp / UV pass, clocks per reading */
	double lamp_travel, uv_travel;	/* ruler counts, first to last reading */
	int lamp_dir, uv_dir;			/* +1 up the ruler, -1 down, 0 not moving */
	const int *cells;			/* ArgyllCMS's trimmed lamp cells: readings per patch */
	const int *counts;			/* UV readings per patch (the cut) */
	int npatch;
	double flat_c, flat_w;		/* the alignment gates' measures (-1 not judged) */
	double align_off, align_rise;	/* the UV pass's measured offset and its sharpness */
	const char *align_state;
	cq_dual_times t;
} cq_dd_pace;

static int cq_dd_dir(const double *p, int n) {
	if (p == NULL || n < 2 || p[n - 1] == p[0])
		return 0;
	return p[n - 1] > p[0] ? 1 : -1;
}

/* "[a,b,c]" of n ints into a malloc'd string (NULL when there is none) */
static char *cq_dd_list(const int *v, int n) {
	char *b;
	size_t at = 0, cap;
	int i;
	if (v == NULL || n <= 0)
		return NULL;
	cap = (size_t)n * 12 + 4;
	if ((b = (char *)malloc(cap)) == NULL)
		return NULL;
	b[at++] = '[';
	for (i = 0; i < n; i++)
		at += (size_t)snprintf(b + at, cap - at, i ? ",%d" : "%d", v[i]);
	b[at++] = ']';
	b[at] = '\0';
	return b;
}

/* ms of a stamp after the lamp pass's readings were in; -1 when unknown */
static long cq_dd_after(unsigned int stamp, unsigned int base) {
	if (stamp == 0 || base == 0)
		return -1;
	return (long)(int)(stamp - base);
}

/* pairing: "checked", "pairing_not_checked" (too dark to judge: the note) or "" */
static void cq_dd_result(const char *what, const char *strip, const char *why, int nuv,
                         const int *counts, int npatch, const cq_dual_uv *u, const char *pairing,
                         int calibrate, const cq_dd_pace *pc) {
	char sb[64], pace[1024];
	char *lc = NULL, *uc = NULL;
	int i, mn = -1;
	cq_json_escape(sb, sizeof(sb), strip != NULL ? strip : "");
	for (i = 0; counts != NULL && i < npatch; i++)
		if (mn < 0 || counts[i] < mn)
			mn = counts[i];
	pace[0] = '\0';
	if (pc != NULL && pc->have) {
		double rs = pc->t.clock_s > 0.0 && pc->clocks > 0 ? pc->clocks * pc->t.clock_s : 0.0;
		unsigned int b = pc->t.lamp_done;
		lc = cq_dd_list(pc->cells, pc->npatch);
		uc = cq_dd_list(pc->counts, pc->npatch);
		snprintf(pace, sizeof(pace),
		         ",\"pace\":true,\"need\":%d,\"edge_steps\":%.2f,\"reading_ms\":%.3f,"
		         "\"lamp_readings\":%d,\"lamp_s\":%.2f,\"lamp_travel\":%.0f,\"lamp_dir\":%d,"
		         "\"uv_s\":%.2f,\"uv_travel\":%.0f,\"uv_dir\":%d,"
		         "\"lamp_off_ms\":%ld,\"uv_dark_ms\":%ld,\"uv_trigger_ms\":%ld,\"uv_done_ms\":%ld,"
		         "\"flatness\":%.6g,\"window_flatness\":%.6g,\"max_window_flatness\":%.6g,"
		         "\"offset_steps\":%.2f,\"offset_rise\":%.3g,\"align\":\"%s\",\"window\":\"%s\"",
		         CQ_DUAL_MIN_UV, cq_dd_edge(pc->align_state), rs * 1000.0,
		         pc->n1, pc->n1 * rs, pc->lamp_travel, pc->lamp_dir,
		         pc->n2 * rs, pc->uv_travel, pc->uv_dir,
		         cq_dd_after(pc->t.lamp_off, b), cq_dd_after(pc->t.uv_dark, b),
		         cq_dd_after(pc->t.uv_trigger, b), cq_dd_after(pc->t.uv_done, b),
		         pc->flat_c == pc->flat_c ? pc->flat_c : -1.0,
		         pc->flat_w == pc->flat_w ? pc->flat_w : -1.0, (double)CQ_DUAL_MAX_EDGE_FLATNESS,
		         pc->align_off, pc->align_rise == pc->align_rise && pc->align_rise < 1e6
		         ? pc->align_rise : -1.0, pc->align_state != NULL ? pc->align_state : "",
		         cq_dd_edge(pc->align_state) >= 0.0 ? "span_less_edge" : "central_60");
	}
	cq_emit_raw("{\"event\":\"dual_pass_result\",\"what\":\"%s\",\"strip\":\"%s\",\"ok\":%s,"
	            "\"why\":\"%s\",\"uv_readings\":%d,\"fewest_per_patch\":%d,\"uv_triggers\":%d,"
	            "\"volts\":[%d,%d],\"pairing\":\"%s\",\"calibrate\":%s%s%s%s%s%s}",
	            what, sb, why == NULL ? "true" : "false", why != NULL ? why : "", nuv, mn,
	            u != NULL ? u->uv_triggers : 0,
	            u != NULL ? u->volts_before : -1, u != NULL ? u->volts_after : -1,
	            pairing != NULL ? pairing : "", calibrate ? "true" : "false", pace,
	            lc != NULL ? ",\"lamp_cells\":" : "", lc != NULL ? lc : "",
	            uc != NULL ? ",\"uv_counts\":" : "", uc != NULL ? uc : "");
	free(lc);
	free(uc);
}

/* 4.3.49: the first reading after a calibration that cannot give M1 / M2 is
 * refused (a misread: calibrate again, then read it again); 1 = refused. The
 * next one, read without a new calibration, is kept as M0 and M1 / M2 end. */
static int cq_dd_ask_calibration(void) {
	if (cq_dd.cal_asked)
		return 0;
	cq_dd.cal_asked = 1;
	return 1;
}

/* the reasons a new calibration can mend */
static int cq_dd_cal_reason(const char *why) {
	return why != NULL && (strcmp(why, "no_dual_calibration") == 0
	    || strcmp(why, "uv_tile_dark") == 0 || strcmp(why, "calibration_mismatch") == 0
	    || strcmp(why, "calibration_mode_changed") == 0);
}

/* (b) a spot reading: after read_sample. A failing UV half makes the patch
 * a misread (it is read again, both halves). */
static void cq_dd_spot(inst_code *rv) {
	cq_dual_lamp l;
	cq_dual_uv u;
	const char *why = NULL;
	cq_dd.n = 0;
	cq_dd.why = "record";
	memset(&u, 0, sizeof(u));
	if (!cq_dd.on)
		return;
	if (*rv != inst_ok && (*rv & inst_mask) != inst_user_trig) {
		i1pro2_cq_dual_arm(cq_dd.it, CQ_DUAL_PHASE_OFF);
		return;
	}
	if (!i1pro2_cq_dual_take_lamp(cq_dd.it, &l) || l.n != 1)
		why = "record";
	i1pro2_cq_dual_arm(cq_dd.it, CQ_DUAL_PHASE_OFF);
	if (why == NULL && (why = cq_dd_fits(0, 0)) == NULL) {
		if (i1pro2_cq_dual_spot_uv(cq_dd.it, &u) != 0 || u.n != 1)
			why = "uv_spot_failed";	/* one unit: lamp and UV half again */
		else if ((why = cq_dd_fits(0, u.clocks)) == NULL)
			why = cq_dd_compute(l.L, u.U, 1, l.clamp);
	}
	i1pro2_cq_dual_arm(cq_dd.it, CQ_DUAL_PHASE_OFF);
	{
		int again = cq_dd_cal_reason(why) && cq_dd_ask_calibration();
		cq_dd_result("spot", "", why, u.n, NULL, 0, &u, "", again, NULL);
		free(l.L);
		free(u.U);
		cq_dd.why = why;
		if (why != NULL) {
			cq_dd.n = 0;
			if (again || cq_dd_pass_level(why))
				*rv = inst_misread;	/* one unit: the patch again (after a calibration) */
		}
	}
}

/* Ruler positions of the two passes from the ruler check's record. */
static int cq_dd_positions(const cq_ruler_rec *r, int n1, int n2, double **lp, double **up) {
	*lp = (double *)malloc(sizeof(double) * (size_t)(n1 > 0 ? n1 : 1));
	*up = (double *)malloc(sizeof(double) * (size_t)(n2 > 0 ? n2 : 1));
	if (*lp == NULL || *up == NULL)
		return 0;
	return cq_dual_positions(r->first, r->nch, r->ch_gap, r->ch_code, r->samples,
	                         n1, n2, r->clocks, *lp, *up);
}

/* SECOND FIX ROUND (2026-11-21): the UV pass lined up with the lamp pass.
 * The driver kept the lamp pass's own 380-400 nm readings; weighted by the
 * tile's T / W there they are what the UV pass must read at the same place
 * (nothing glows below 410 nm). cq_dual_align finds the offset, the UV
 * positions are corrected by it. Without those readings (cannot happen on
 * the instrument path, only if memory ran out) the strip is cut uncorrected,
 * as before the fix round, and the log says so (state "not_measured"). With
 * nothing clear to line up by (CQ_DUAL_NOT_LINED_UP) it is cut uncorrected
 * with 4.3.54's central window (state "not_lined_up"). */
static const char *cq_dd_align(int npatch, const int (*cells)[2], int n1, const double *lp,
                               int nuv, double *up, const double *U,
                               double *off, double *rise, const char **state) {
	double *ls = NULL, *lsig = NULL, *usig = NULL, lo = 0.0, hi = 0.0;
	int nls = 0, nl, i, k;
	const char *why = NULL;
	*state = "not_measured";
	if (!i1pro2_cq_dual_take_lamp_readings(cq_dd.it, &ls, &nls) || nls <= 1)
		return NULL;
	nl = nls < n1 ? nls : n1;
	lsig = (double *)malloc(sizeof(double) * (size_t)(nl > 0 ? nl : 1));
	usig = (double *)malloc(sizeof(double) * (size_t)(nuv > 0 ? nuv : 1));
	if (lsig == NULL || usig == NULL) {
		free(ls); free(lsig); free(usig);
		return NULL;
	}
	for (i = 0; i < nl; i++) {
		double a = 0.0;
		for (k = 0; k < CQ_DUAL_LS_BANDS; k++)
			a += ls[i * CQ_DUAL_LS_BANDS + k] * cq_dd.cal.T[k] / cq_dd.cal.W[k];
		lsig[i] = a / (double)CQ_DUAL_LS_BANDS;
	}
	for (i = 0; i < nuv; i++) {
		double a = 0.0;
		for (k = 0; k < CQ_DUAL_LS_BANDS; k++)
			a += U[i * CQ_DUAL_NB + k];
		usig[i] = a / (double)CQ_DUAL_LS_BANDS;
	}
	for (k = 0; k < npatch; k++) {
		int s = cells[k][0], n = cells[k][1];
		double a, b;
		if (n < 1 || s < 0 || s + n > n1)
			continue;
		a = lp[s];
		b = lp[s + n - 1];
		if (k == 0 || (a < b ? a : b) < lo) lo = a < b ? a : b;
		if (k == 0 || (a < b ? b : a) > hi) hi = a < b ? b : a;
	}
	why = cq_dual_align(nl, lp, lsig, nuv, up, usig, lo, hi, off, rise);
	if (why != NULL && strcmp(why, CQ_DUAL_NOT_LINED_UP) == 0) {
		*state = "not_lined_up";	/* cut uncorrected with 4.3.54's window (header) */
		why = NULL;
		*off = 0.0;
	} else {
		*state = why == NULL ? "lined_up" : "refused";
		if (why == NULL)
			for (i = 0; i < nuv; i++)
				up[i] -= *off;
	}
	free(ls); free(lsig); free(usig);
	return why;
}

/* (c) a hand strip, right after the lamp pass's read_strip. */
static void cq_dd_strip(inst *it, const char *strip, inst_code *rv, int npatch, int sguide,
                        double pwid, double gwid, double twid) {
	cq_dual_lamp l;
	cq_dual_uv u;
	cq_ruler_rec r;
	ipatch *v2 = NULL;
	double *lp = NULL, *up = NULL, *cutv = NULL;
	int *counts = NULL;
	inst_code rv2;
	int lamp_ok, got_r = 0, calibrate = 0;
	double flat_c = -1.0, flat_w = -1.0;	/* -1: not measured / not judged */
	double align_off = 0.0, align_rise = -1.0;	/* the UV pass's measured offset */
	const char *align_state = "not_reached";
	const char *why = NULL, *pairing = "";
	char sb[64];

	cq_dd.n = 0;
	cq_dd.why = "record";
	memset(&u, 0, sizeof(u));
	memset(&r, 0, sizeof(r));
	if (!cq_dd.on)
		return;
	lamp_ok = *rv == inst_ok;
	if (!i1pro2_cq_dual_take_lamp(it, &l))
		memset(&l, 0, sizeof(l));
	/* an aborted or commanded lamp pass ends here (nothing to close: a
	 * lamp pass that never triggered started no ruler stream) */
	if ((*rv & inst_mask) == inst_user_abort) {
		cq_dd.uncal = NULL;
		i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_OFF);
		free(l.L);
		return;
	}
	cq_json_escape(sb, sizeof(sb), strip);
	/* 4.3.49: the last calibration cannot give M1 / M2, so the strip loop
	 * read this strip as a plain lamp scan (no ruler stream: no second pass
	 * is due). The first such strip after that calibration is refused with
	 * "calibrate again" (a misread: read again); read again without a new
	 * calibration, it is kept as M0 and M1 / M2 end, as before. */
	if (cq_dd.uncal != NULL) {
		const char *cw = cq_dd.uncal;
		int again;
		cq_dd.uncal = NULL;
		i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_OFF);
		free(l.L);
		if (*rv != inst_ok)
			return;			/* ArgyllCMS's own misread: read again, as always */
		again = cq_dd_ask_calibration();
		cq_dd_result("strip", strip, cw, 0, NULL, 0, NULL, "", again, NULL);
		cq_dd.why = cw;
		cq_dd.n = 0;
		if (again)
			*rv = inst_misread;	/* calibrate again, then the strip again */
		return;
	}
	/* pass 2 of 2 only as a RECORDED form (safety review 2026-11-18, M2): the
	 * lamp pass counted readings in a ruler stream that still runs, so the UV
	 * trigger carries "ruler end" (0x0209) and closes it. Otherwise (the lamp
	 * pass's trigger or read failed, the ruler was given up, or a UV pass was
	 * left with Esc and this lamp pass could not start a stream) no UV pass
	 * can be lined up with this or any later lamp pass: M1 / M2 end for the
	 * session, M0 goes on; a stream left running is drained until the close,
	 * as the ruler check does. The driver refuses such a UV trigger too. */
	if (!i1pro2_cq_dual_uv_pass_ready(it)) {
		i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_OFF);
		free(l.L);
		cq_dd_result("strip", strip, "dual_needs_ruler", 0, NULL, 0, NULL, "", 0, NULL);
		cq_dd.why = "dual_needs_ruler";
		cq_dd.on = 0;
		cq_cond_lose("dual_dual_needs_ruler");
		return;
	}
	/* the helper asks for it itself. After a lamp pass ArgyllCMS did not
	 * recognise (lamp_ok false) the same recorded UV trigger is still the only
	 * form that closes the ruler stream, so the helper waits for it as before;
	 * since 4.3.58 (item 17, approved as a direction by Basti, 23 Nov 2026)
	 * the app asks for ONE press in place there, not a second pass, answers
	 * the misread that follows with Retry itself, and asks for pass 1 again.
	 * Nothing changes on the wire; only the blue is not sent then. */
	cq_emit_raw("{\"event\":\"dual_pass\",\"strip\":\"%s\",\"pass\":\"uv\",\"of\":2,"
	            "\"lamp_ok\":%s}", sb, lamp_ok ? "true" : "false");
	/* 4.3.52: the blue "second pass due" (lights Beta, result signals, an
	 * i1Pro 2): due a moment after pass 1, sent from the wait below */
	cq_lights_second_pass_due(lamp_ok);
	/* 4.3.49: a calibration asked for during this wait runs at the next
	 * strip prompt (never over the open ruler stream), and a command that
	 * would leave the wait (a jump, a move) is held: the wait goes on */
	cq_cal_gate_set(0);
	if ((v2 = (ipatch *)calloc((size_t)npatch, sizeof(ipatch))) == NULL)
		rv2 = inst_internal_error;
	else for (;;) {
		int held;
		i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_UV);
		rv2 = it->read_strip(it, "STRIP", npatch, (char *)strip, sguide, pwid, gwid, twid, v2);
		if ((rv2 & inst_mask) != inst_user_abort || (held = cq_dd_held_command()) == 0)
			break;
		i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_OFF);
		cq_emit_raw("{\"event\":\"dual_pass_held\",\"strip\":\"%s\",\"cmd\":\"%s\"}", sb,
		            held == 'g' || held == 'G' ? "goto" : held == 'm' ? "file_as"
		            : held == 'u' ? "turn" : held == 'n' || held == 'N' ? "next_unread"
		            : held == 'b' || held == 'B' ? "back" : "forward");
	}
	i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_OFF);	/* the UV switch off on every way out */
	cq_lights_second_pass_over();	/* 4.3.52: a blue not sent by now is skipped */
	free(v2);
	(void)i1pro2_cq_dual_take_uv(it, &u);
	got_r = i1pro2_cq_ruler_take(it, &r);

	if (!lamp_ok)
		why = "lamp";
	else if ((rv2 & inst_mask) == inst_user_abort) {
		*rv = rv2;				/* the loop handles the key or command */
		why = "uv_pass_missing";
	} else if (u.nread > CQ_DUAL_MAX_UV_READINGS)
		why = "uv_pass_too_long";	/* refused whole (S3): move a little faster */
	else if (rv2 != inst_ok || u.n <= 0)
		why = "uv_pass_missing";
	else if ((why = cq_dd_fits(1, u.clocks)) != NULL)
		calibrate = cq_dd_cal_reason(why) && cq_dd_ask_calibration();
	else if (l.n != npatch || l.L == NULL)
		why = "record";
	else if (!got_r || !r.valid || r.ended != CQ_RULER_END_SHORT || r.ncut != npatch
	      || r.clocks <= 0)
		why = "dual_needs_ruler";
	if (why == NULL) {
		int n1, k;
		/* the lamp pass's readings (the driver kept the count at the lamp
		 * pass's end); the UV pass's are the stream's last ones */
		n1 = i1pro2_cq_dual_lamp_count(it);
		if (n1 <= 0 || !cq_dd_positions(&r, n1, u.n, &lp, &up))
			why = "no_ruler";
		else if ((cutv = (double *)malloc(sizeof(double) * CQ_DUAL_NB * (size_t)npatch)) == NULL
		      || (counts = (int *)malloc(sizeof(int) * (size_t)npatch)) == NULL)
			why = "memory";
		else {
			int (*cells)[2] = (int (*)[2])malloc(sizeof(int) * 2 * (size_t)npatch);
			if (cells == NULL)
				why = "memory";
			else {
				for (k = 0; k < npatch; k++) {
					cells[k][0] = r.cut_ss[k];
					cells[k][1] = r.cut_no[k];
				}
				/* second fix round of 2026-11-21: line the UV pass up with the lamp
				 * pass by their 380-400 nm readings (cq_dual_align), then cut */
				why = cq_dd_align(npatch, (const int (*)[2])cells, n1, lp, u.n, up, u.U,
				                  &align_off, &align_rise, &align_state);
				if (why == NULL)
				why = cq_dual_cut(CQ_DUAL_NB, npatch, (const int (*)[2])cells, n1, lp,
				                  u.n, up, u.U, CQ_DUAL_TRIM, CQ_DUAL_MIN_UV,
				                  cq_dd_edge(align_state), cutv, counts);
				/* fix round of 2026-11-21: both alignment measures for the log */
				flat_c = cq_dual_flatness(CQ_DUAL_NB, npatch, (const int (*)[2])cells, lp,
				                          u.n, up, u.U, CQ_DUAL_TRIM);
				flat_w = cq_dd_edge(align_state) >= 0.0
				         ? cq_dual_window_flatness(CQ_DUAL_NB, npatch, (const int (*)[2])cells,
				                                   lp, u.n, up, u.U, CQ_DUAL_EDGE_STEPS) : -1.0;
				free(cells);
				if (strcmp(align_state, "refused") == 0) {
					free(counts);		/* no cut was made: no counts to report */
					counts = NULL;
				}
			}
		}
		/* the UV pass belongs to THIS strip (safety review 2026-11-18, M1):
		 * a pass over the neighbouring row, or set down one patch further,
		 * passes every ruler gate; only its LED light at 380-400 nm, which
		 * must follow (T / W) x this lamp pass, tells it apart */
		if (why == NULL) {
			cq_dual_pairing_ev pe;
			why = cq_dual_pairing(&cq_dd.cal, npatch, l.L, cutv, &pe);
			if (why == NULL)
				pairing = pe.checked ? "checked" : "pairing_not_checked";
		}
		if (why == NULL)
			why = cq_dd_compute(l.L, cutv, npatch, l.clamp);
	}
	{	/* after 4.3.54: the pace (readings, times, travel, per patch) */
		cq_dd_pace pc;
		memset(&pc, 0, sizeof(pc));
		pc.n1 = i1pro2_cq_dual_lamp_count(it);
		pc.n2 = u.n;
		pc.clocks = u.clocks > 0 ? u.clocks : r.clocks;
		i1pro2_cq_dual_times(it, &pc.t);
		if (lp != NULL && up != NULL && pc.n1 > 1 && pc.n2 > 1) {
			pc.have = 1;
			pc.lamp_travel = fabs(lp[pc.n1 - 1] - lp[0]);
			pc.uv_travel = fabs(up[pc.n2 - 1] - up[0]);
			pc.lamp_dir = cq_dd_dir(lp, pc.n1);
			pc.uv_dir = cq_dd_dir(up, pc.n2);
			pc.flat_c = flat_c;
			pc.flat_w = flat_w;
			pc.align_off = align_off;
			pc.align_rise = align_rise;
			pc.align_state = align_state;
			if (counts != NULL && got_r && r.ncut == npatch) {
				pc.cells = r.cut_no;
				pc.counts = counts;
				pc.npatch = npatch;
			}
		}
		cq_dd_result("strip", strip, why, u.n, why == NULL || counts != NULL ? counts : NULL,
		             counts != NULL ? npatch : 0, &u, pairing, calibrate, &pc);
	}
	free(l.L);
	free(u.U);
	free(lp);
	free(up);
	free(cutv);
	free(counts);
	cq_ruler_rec_clear(&r);
	cq_dd.why = why;
	if (why != NULL) {
		cq_dd.n = 0;
		if (*rv == inst_ok && (calibrate || cq_dd_pass_level(why)))
			*rv = inst_misread;	/* both passes again (after a new calibration) */
	}
}
