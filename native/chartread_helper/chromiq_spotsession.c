/* chromiq_spotsession.c: Tools > Read single patches, read by ChromIQ's own
 * helper (item 43 steps 2-3, 2026-11-24).
 *
 *   chromiq-chartread --json --spot-session [--spot-conditions]
 *       [--dual-scale <s> --dual-scale-source <w> --dual-white <w>
 *        --dual-chosen M0|M1|M2] [-c <port>] [-N] [-H]
 *
 * Included ONCE by chromiq_chartread.c, before main (it uses that file's
 * statics). Without --spot-session nothing here runs and every other mode of
 * the helper is unchanged.
 *
 * WHAT IT IS. ArgyllCMS's spotread does one thing this cannot do without:
 * it hands back ONE condition per reading. This session reads the same way
 * the helper reads a chart patch by patch, with no chart and no file:
 *   - an i1Pro 3 with --spot-conditions keeps M0, M1 and M2 of every press
 *     (the driver works all three out of the one reading it always makes:
 *     i1pro3_cq_cond_*, arithmetic only, nothing new on the wire);
 *   - an i1Pro 2 with --spot-conditions and --dual-scale reads the DUAL SPOT
 *     (cq_dd_spot: the lamp reading, then the UV half on the same spot, one
 *     unit) after a dual calibration (cq_dd_after_cal), and keeps M0 (the
 *     lamp reading) with M1 and M2 worked out of both halves;
 *   - anything else reads M0 alone, as a spot reading always did.
 *
 * WHAT GOES TO THE INSTRUMENT IS THE PATCH-BY-PATCH READER'S, BY
 * CONSTRUCTION. The open, the mode, the start calibration, the trigger mode,
 * every press (cq_spot_read_once, the very function the chart's patch loop
 * calls) and every calibration asked for (cq_requested_calibration) are the
 * chart reader's own calls in the chart reader's own order. Two choices of
 * its own, neither a new request form:
 *   (1) a dual session whose start has no dual calibration yet asks for the
 *       start-up calibration a dual STRIP session asks for
 *       (cq_dual_startup_calt, section 19 of docs/design/i1pro2_dual_scan.md:
 *       everything a normal start needs, and the white in any case). The
 *       i1Pro 2's driver wants its start calibration in every session that
 *       was not started with -N (want_calib), so this is the patch-by-patch
 *       reader's start request too, request for request;
 *   (2) -N (skip the start calibration) and -H (high resolution) end the
 *       dual part before anything is sent (a dual spot needs the dual tile,
 *       and the factory tables exist only at 10 nm); M0 goes on, and the UV
 *       light is never asked for.
 * tests/test_spot_session_wire.py runs this file and the patch-by-patch
 * reader through the REAL i1Pro 2 driver on a fake USB layer
 * (tests/spot_session_wire_test.c) and compares the two, request for
 * request.
 *
 * The UV light: lit only during a UV trigger inside cq_dd_spot, which
 * disarms on every way out of a reading; this file disarms once more, and
 * switches the dual part off, on every way out of the session (a stop, an
 * error, the end of stdin, a lost USB connection) before the instrument is
 * let go.
 *
 * Events (one JSON object per line; "t" is this process's msec clock):
 *   spot_session_start {build}
 *   instrument {model}, filter {filter}, wavelength (i1Pro 2, the log only)
 *   conditions {active, ...} as the chart reader says it
 *   cal_required / cal_done / cal_result / dual_calibration as patch by patch
 *   spot_ready {n}         waiting for a press (or {"cmd":"read"})
 *   spot_reading {n, XYZ, Lab, spec, main, conditions{M1,M2}}
 *   dual_pass_result       an i1Pro 2 dual spot's verdict (cq_dd_result)
 *   error {kind, detail}   misread (read again), coms (the session ends)
 *   spot_session_end {why}
 * Commands: {"cmd":"read"}, {"cmd":"calibrate"} (+ "ok" / "cal_cancel" at its
 * prompt), {"cmd":"quit"} or the end of stdin.
 * AGPL-3.0 like the rest of the helper (see ../instlib/License.txt). */

/* XYZ (0..100) to D50 L*a*b*, as spotread prints it */
static void cq_ss_lab(const double xyz[3], double lab[3]) {
	double x[3];
	int j;
	for (j = 0; j < 3; j++)
		x[j] = xyz[j] / 100.0;
	icmXYZ2Lab(&icmD50, lab, x);
}

/* ,"spec":{...} of one spectrum, appended to b (no-op without one) */
static void cq_ss_spec(char *b, size_t cap, int n, double ws, double wl, double norm,
                       const double *v) {
	size_t at = strlen(b);
	int j;
	if (n <= 0 || n > CQ_CX_MAXB || v == NULL)
		return;
	at += (size_t)snprintf(b + at, cap > at ? cap - at : 0,
	                       ",\"spec\":{\"short\":%.1f,\"long\":%.1f,\"norm\":%.6g,\"v\":[",
	                       ws, wl, norm);
	for (j = 0; j < n && at < cap; j++)
		at += (size_t)snprintf(b + at, cap - at, j ? ",%.6g" : "%.6g", v[j]);
	if (at < cap)
		snprintf(b + at, cap - at, "]}");
}

/* "XYZ":[..],"Lab":[..](,"spec":{..}) of one value */
static void cq_ss_value(char *b, size_t cap, const double xyz[3], int n, double ws,
                        double wl, double norm, const double *v) {
	double lab[3];
	cq_ss_lab(xyz, lab);
	snprintf(b, cap, "\"XYZ\":[%.6f,%.6f,%.6f],\"Lab\":[%.6f,%.6f,%.6f]",
	         xyz[0], xyz[1], xyz[2], lab[0], lab[1], lab[2]);
	cq_ss_spec(b, cap, n, ws, wl, norm, v);
}

/* the conditions of this session (the chart reader's cq_cond_for_session,
 * without its files: the record of ONE reading, cq_vx, is all it needs) */
static void cq_ss_conditions(inst *it, int nocal, int highres) {
	const char *why = NULL;
	cq_cond_active = 0;
	cq_cond_keep = 0;
	cq_cond_keep_empty = 0;
	cq_cond_m0only = 0;
	cq_cond_it = NULL;
	cq_cond_replay = 0;
	cq_cond_dual = 0;
	cq_cond_main = 0;			/* no -F: the reading itself is M0 */
	if (!cq_spot_conditions) {
		cq_emit_raw("{\"event\":\"conditions\",\"active\":false,\"why\":\"off\"}");
		return;
	}
	if (it == NULL)
		why = "instrument";
	else if (cq_dual_req && it->dtype == instI1Pro2) {
		if (nocal)
			why = "dual_nocal";		/* a dual spot needs the dual tile */
		else if (highres)
			why = "dual_high_resolution";	/* the tables exist at 10 nm only */
		else if (cq_replay_active()) {
			if (!cq_replay_dual_ready())
				why = "dual_not_available";
			else {
				cq_cond_replay = 1;
				cq_cond_dual = 1;
			}
		} else if ((why = cq_dd_start(it)) == NULL) {
			cq_cond_dual = 1;
			cq_cal_done_hook = cq_dd_cal_hook;
		}
	} else if (cq_replay_active()) {
		if (!cq_replay_cond_ready())
			why = "instrument";
		else
			cq_cond_replay = 1;
	} else if (it->dtype != instI1Pro3 || !i1pro3_cq_cond_options(it, 1))
		why = "instrument";
	if (why != NULL) {
		if (it != NULL && !cq_replay_active() && it->dtype == instI1Pro3)
			i1pro3_cq_cond_options(it, 0);
		if (cq_dd.on) {			/* the device side off again */
			i1pro2_cq_dual_arm(cq_dd.it, CQ_DUAL_PHASE_OFF);
			(void)i1pro2_cq_dual_options(cq_dd.it, 0, NULL, NULL);
			cq_dd.on = 0;
		}
		cq_cal_done_hook = NULL;
		cq_cond_dual = 0;
		cq_emit_raw("{\"event\":\"conditions\",\"active\":false,\"why\":\"%s\"}", why);
		return;
	}
	cq_cond_it = it;
	cq_cond_active = 1;
	if (cq_cond_dual) {
		char sb[32];
		snprintf(sb, sizeof(sb), "%.4f", cq_dual_scale);
		cq_emit_raw("{\"event\":\"conditions\",\"active\":true,\"instrument\":\"i1pro2\","
		            "\"dual\":true,\"scale\":%s,\"scale_source\":\"%s\",\"white\":\"%s\","
		            "\"main\":\"M0\",\"extra\":[\"M1\",\"M2\"],\"chosen\":\"%s\"}",
		            sb, cq_dual_source, cq_dual_white, cq_dual_chosen);
	} else
		cq_emit_raw("{\"event\":\"conditions\",\"active\":true,\"instrument\":\"i1pro3\","
		            "\"main\":\"M0\",\"extra\":[\"M1\",\"M2\"]}");
}

/* the reading of one press, as one event; 0 when it has no value (a
 * misread is said instead) */
static int cq_ss_emit_reading(int n, ipatch *val) {
	static char mb[4096], c1[4096], c2[4096];
	char *out;
	size_t cap;
	int have = cq_cond_active && cq_vx_valid && cq_vx_n == 1 && cq_vx != NULL;
	mb[0] = c1[0] = c2[0] = '\0';
	if (!val->XYZ_v) {
		cq_emit_error("misread", "no XYZ");
		return 0;
	}
	cq_ss_value(mb, sizeof(mb), val->XYZ, val->sp.spec_n, val->sp.spec_wl_short,
	            val->sp.spec_wl_long, val->sp.norm, val->sp.spec);
	if (have) {
		cq_cx_val *a = &cq_vx[0][1], *b = &cq_vx[0][2];
		if (a->v)
			cq_ss_value(c1, sizeof(c1), a->XYZ, a->spec_n, a->wl_short, a->wl_long,
			            a->norm, a->spec);
		if (b->v)
			cq_ss_value(c2, sizeof(c2), b->XYZ, b->spec_n, b->wl_short, b->wl_long,
			            b->norm, b->spec);
	}
	cap = strlen(mb) + strlen(c1) + strlen(c2) + 256;
	if ((out = (char *)malloc(cap)) == NULL)
		return 0;
	snprintf(out, cap, "{\"event\":\"spot_reading\",\"n\":%d,\"main\":\"M0\",%s"
	         ",\"dual\":%s,\"conditions\":{%s%s%s%s%s%s%s}}",
	         n, mb, cq_cond_active && cq_cond_dual ? "true" : "false",
	         c1[0] ? "\"M1\":{" : "", c1, c1[0] ? "}" : "",
	         c1[0] && c2[0] ? "," : "",
	         c2[0] ? "\"M2\":{" : "", c2, c2[0] ? "}" : "");
	cq_emit_raw("%s", out);
	free(out);
	return 1;
}

/* every way out: the UV state and the conditions off, then the instrument
 * let go (the exit guard covers a signal in the middle of the close) */
static int cq_ss_end(inst *it, icompaths *icmps, const char *why, int rc) {
	if (cq_dd.on) {
		i1pro2_cq_dual_arm(cq_dd.it, CQ_DUAL_PHASE_OFF);
		(void)i1pro2_cq_dual_options(cq_dd.it, 0, NULL, NULL);
		cq_dd.on = 0;
	}
	cq_cal_done_hook = NULL;
	if (it != NULL && !cq_replay_active() && it->dtype == instI1Pro3)
		i1pro3_cq_cond_options(it, 0);
	cq_cond_active = 0;
	cq_cal_gate_set(0);
	/* said before the close: a close that blocks is ended by the exit guard */
	cq_emit_raw("{\"event\":\"spot_session_end\",\"why\":\"%s\"}", why);
	if (it != NULL)
		it->del(it);
	if (icmps != NULL)
		icmps->del(icmps);
	return rc;
}

static int cq_run_spot_session(int comport, flow_control fc, int nocal, int highres) {
	icompaths *icmps = NULL;
	icompath *ipath = NULL;
	inst *it = NULL;
	inst_mode cap = 0, mode;
	inst2_capability cap2 = 0;
	inst3_capability cap3 = 0;
	inst_code rv;
	ipatch val;
	int n = 0;

	if (!cq_json) {
		fprintf(stderr, "--spot-session needs --json\n");
		return 1;
	}
	if (cq_i1pro2_lights || cq_ruler || cq_tscan_dir != NULL || cq_presswait
	 || cq_button_test || cq_cond_dir != NULL) {
		cq_emit_error("spot_options", "--spot-session cannot be combined with that option");
		return 1;
	}
	cq_emit_raw("{\"event\":\"spot_session_start\",\"t\":%u,\"build\":\"%s\"}", msec_time(),
	            cq_helper_build_string());

	inst_reset_uih();
	if (cq_replay_active())
		it = cq_new_replay_inst(g_log, cq_uicallback, inst_get_uicontext());
	else {
#ifdef CQ_FAKE_USB_TEST
		it = cq_test_new_inst(g_log, cq_uicallback, inst_get_uicontext());
#else
		if ((icmps = new_icompaths(g_log)) != NULL)
			ipath = icmps->get_path(icmps, comport);
		if (ipath != NULL)
			it = new_inst(ipath, 0, g_log, cq_uicallback, inst_get_uicontext());
#endif
	}
	if (it == NULL) {
		cq_emit_error("no_instrument", "");
		return cq_ss_end(NULL, icmps, "no_instrument", 1);
	}
	cq_guard_inst(it);	/* always let the instrument go */
	it->set_event_callback(it, cq_event_callback, (void *)it);
	if ((rv = it->init_coms(it, baud_38400, fc, 15.0)) != inst_ok
	 || (rv = it->init_inst(it)) != inst_ok) {
		cq_emit_error("no_instrument", it->interp_error(it, rv));
		return cq_ss_end(it, icmps, "no_instrument", 1);
	}
	cq_exit_guard_signals();

	cq_emit_raw("{\"event\":\"instrument\",\"model\":\"%s\",\"chart_model\":\"\"}",
	            inst_name(it->get_itype(it)));
	cq_emit_wavelength(it, "open");

	it->capabilities(it, &cap, &cap2, &cap3);
	if (!IMODETST(cap, inst_mode_reflection)
	 || it->check_mode(it, inst_mode_ref_spot) != inst_ok) {
		cq_emit_error("spot_mode", "the instrument cannot read reflective spots");
		return cq_ss_end(it, icmps, "spot_mode", 1);
	}
	if (nocal != 0 && it->get_set_opt(it, inst_opt_noinitcalib, 0) != inst_ok)
		printf("Disable inital-calibrate not supported\n");
	/* the filter the i1Pro family reads through, as the chart reader says it */
	if (it->dtype == instI1Pro || it->dtype == instI1Pro2 || it->dtype == instI1Pro3) {
		inst_opt_filter pf = inst_opt_filter_unknown;
		const char *pn = "unknown";
		if (it->get_set_opt(it, inst_stat_get_filter, &pf) == inst_ok) {
			if (pf == inst_opt_filter_none) pn = "none";
			else if (pf == inst_opt_filter_UVCut) pn = "uvcut";
			else if (pf == inst_opt_filter_D50) pn = "d50";
			else if (pf == inst_opt_filter_D65) pn = "d65";
			else if (pf == inst_opt_filter_pol) pn = "polarised";
		}
		cq_emit_raw("{\"event\":\"filter\",\"filter\":\"%s\"}", pn);
	}
	mode = inst_mode_ref_spot;
	if (IMODETST(cap, inst_mode_spectral))
		mode |= inst_mode_spectral;
	if (highres && IMODETST(cap, inst_mode_highres))
		mode |= inst_mode_highres;
	if ((rv = it->set_mode(it, mode)) != inst_ok) {
		cq_emit_error("spot_mode", it->interp_error(it, rv));
		return cq_ss_end(it, icmps, "spot_mode", 1);
	}
	it->capabilities(it, &cap, &cap2, &cap3);
	if (!cq_replay_active()) {	/* read-only: which USB step failed (4.3.36) */
		if (it->dtype == instI1Pro || it->dtype == instI1Pro2)
			cq_usbwatch_install(it->icom, CQ_UW_I1PRO);
		else if (it->dtype == instI1Pro3)
			cq_usbwatch_install(it->icom, CQ_UW_I1PRO3);
	}
	cq_ss_conditions(it, nocal, highres);

	/* the start calibration: the patch-by-patch reader's, and for a dual
	 * session without a dual tile yet the dual strip reader's (header) */
	rv = inst_ok;
	if (nocal == 0 && cq_dd.on && !cq_dd.cal.have_uv_tile)
		rv = cq_handle_calibrate(it, cq_dual_startup_calt(it->needs_calibration(it)),
		                         inst_calc_none, 0);
	else if (nocal == 0 && (it->needs_calibration(it) & inst_calt_n_dfrble_mask))
		rv = cq_handle_calibrate(it, inst_calt_needed, inst_calc_none, 0);
	if (rv != inst_ok) {
		if ((rv & inst_mask) != inst_user_abort)
			cq_emit_error("cal_failed", it->inst_interp_error(it, rv));
		return cq_ss_end(it, icmps, (rv & inst_mask) == inst_user_abort ? "stopped"
		                                                                 : "calibration", 1);
	}

	/* the trigger: the instrument's button, or {"cmd":"read"} */
	if (cap2 & inst2_user_switch_trig)
		rv = it->get_set_opt(it, inst_opt_trig_user_switch);
	else if (cap2 & inst2_user_trig)
		rv = it->get_set_opt(it, inst_opt_trig_user);
	else
		rv = inst_unsupported;
	if (rv != inst_ok) {
		cq_emit_error("spot_trigger", it->interp_error(it, rv));
		return cq_ss_end(it, icmps, "trigger", 1);
	}
	inst_set_uih('k', 'k', DUIH_CMND);
	inst_set_uih('K', 'K', DUIH_CMND);
	inst_set_uih('q', 'q', DUIH_ABORT);
	inst_set_uih('Q', 'Q', DUIH_ABORT);
	inst_set_uih(0x1b, 0x1b, DUIH_ABORT);
	inst_set_uih(0xd, 0xd, DUIH_TRIG);	/* {"cmd":"read"} */
	inst_set_uih(' ', ' ', DUIH_TRIG);

	for (;;) {
		cq_emit_raw("{\"event\":\"spot_ready\",\"t\":%u,\"n\":%d,\"conditions\":%s}",
		            msec_time(), n + 1, cq_cond_live() ? "true" : "false");
		if (cq_replay_active())
			cq_replay_arm_spot_n(n);
		memset(&val, 0, sizeof(val));
		rv = cq_spot_read_once(it, &val);
		if (cq_stdin_eof && (rv & inst_mask) == inst_user_abort)
			return cq_ss_end(it, icmps, "stdin", 0);
		if (rv == inst_ok || (rv & inst_mask) == inst_user_trig) {
			if (cq_ss_emit_reading(n + 1, &val))
				n++;
			continue;
		}
		if ((rv & inst_mask) == inst_user_abort) {
			int keyc = inst_get_uih_char();
			if ((keyc & DUIH_CMND) && ((keyc & 0xff) == 'k' || (keyc & 0xff) == 'K')) {
				if (cq_requested_calibration(it) != 0)
					return cq_ss_end(it, icmps, "stopped", 0);
				continue;
			}
			if (keyc & DUIH_ABORT)
				return cq_ss_end(it, icmps, "stopped", 0);
			continue;
		}
		if ((rv & inst_mask) == inst_needs_cal) {
			inst_code ev = cq_handle_calibrate(it, inst_calt_needed, inst_calc_none, 0);
			if (ev != inst_ok)
				return cq_ss_end(it, icmps, (ev & inst_mask) == inst_user_abort
				                            ? "stopped" : "calibration", 1);
			continue;
		}
		if ((rv & inst_mask) == inst_coms_fail) {
			cq_emit_coms_error(it, rv);
			return cq_ss_end(it, icmps, "coms", 1);
		}
		/* a misread (a dual spot whose half failed is one too) or another
		 * error: nothing is kept, the same spot is read again */
		cq_emit_error("misread", it->interp_error(it, rv));
	}
}
