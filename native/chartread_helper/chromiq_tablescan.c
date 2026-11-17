/* chromiq_tablescan.c: the helper's "table scan" mode for an i1Pro 2 seated
 * in an X-Rite i1iO 2 table (study, 2026-11-16; NOT wired into ChromIQ's UI).
 *
 *   chromiq-chartread --json --i1io-table-scan <out-dir> [-c <port>]
 *
 * Without --i1io-table-scan nothing in this file runs and the helper is the
 * 2026-11-15e helper, wire byte for wire byte (tests/test_i1io_table_scan.py).
 *
 * The helper drives ONLY the instrument. The table belongs to the tester
 * program (its own USB connection); the two meet over this process's stdin
 * and stdout. The instrument's part of one row scan is what X-Rite's
 * i1Profiler 3.8.6 sent in four USB recordings (see native/instlib/cq_tscan.h).
 *
 * Commands (one JSON object per line; numbers may be bare or quoted):
 *   {"cmd":"tscan_calibrate"}            ArgyllCMS's strip-mode calibration
 *                                        (cal_* events as in a measurement)
 *   {"cmd":"tscan_lights_off"}           the recorded lights-off, before c4
 *   {"cmd":"tscan_arm","n":520,"wait_ms":3000}
 *                                        wait (at most wait_ms) until a pass of
 *                                        n readings can be fired AT ONCE:
 *                                        calibrated, lamp dark >= 1.07 s,
 *                                        lights-off >= 0.68 s ago. Answers
 *                                        tscan_armed {"ready":true|false}
 *   {"cmd":"tscan_fire","n":520,"patches":28,"name":"row1"}
 *                                        dark + lit pass + status, at once and
 *                                        always to the end (no cancel point);
 *                                        answers tscan_firing at once, then
 *                                        tscan_fired with every time and the
 *                                        files written: <name>.raw (the dark
 *                                        and lit readings as received),
 *                                        <name>.spec.csv (every reading's
 *                                        calibrated spectrum), <name>.rec.csv
 *                                        (ArgyllCMS's recognised patches, when
 *                                        it found them), <name>.json
 *   {"cmd":"tscan_quit"} or end of stdin the instrument is let go
 * Every event carries "t": this process's msec clock, for the tester's log.
 * AGPL-3.0 like the rest of the helper (see ../instlib/License.txt). */

#ifdef SALONEINSTLIB
#include "sa_config.h"
#else
#include "aconfig.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#ifndef NT
#include <pthread.h>
#endif
#include "numsup.h"
#include "cgats.h"
#include "xspect.h"
#include "insttypes.h"
#include "conv.h"
#include "icoms.h"
#include "inst.h"
#include "instappsup.h"
#include "chromiq_ext.h"
#include "cq_tscan.h"

#define CQ_TS_Q 8
static char cq_ts_q[CQ_TS_Q][256];
static volatile int cq_ts_head = 0, cq_ts_tail = 0;
#ifdef NT
static CRITICAL_SECTION cq_ts_lock;
static int cq_ts_lock_init = 0;
#define TS_LOCK()   EnterCriticalSection(&cq_ts_lock)
#define TS_UNLOCK() LeaveCriticalSection(&cq_ts_lock)
#else
static pthread_mutex_t cq_ts_lock = PTHREAD_MUTEX_INITIALIZER;
#define TS_LOCK()   pthread_mutex_lock(&cq_ts_lock)
#define TS_UNLOCK() pthread_mutex_unlock(&cq_ts_lock)
#endif

/* Called on the command thread for every "tscan_*" command. */
static void cq_ts_push(const char *line) {
	int next;
	TS_LOCK();
	next = (cq_ts_head + 1) % CQ_TS_Q;
	if (next != cq_ts_tail) {
		strncpy(cq_ts_q[cq_ts_head], line, sizeof(cq_ts_q[0]) - 1);
		cq_ts_q[cq_ts_head][sizeof(cq_ts_q[0]) - 1] = '\0';
		cq_ts_head = next;
	}
	TS_UNLOCK();
}

static int cq_ts_take(char *out, int size) {
	int got = 0;
	TS_LOCK();
	if (cq_ts_head != cq_ts_tail) {
		strncpy(out, cq_ts_q[cq_ts_tail], size - 1);
		out[size - 1] = '\0';
		cq_ts_tail = (cq_ts_tail + 1) % CQ_TS_Q;
		got = 1;
	}
	TS_UNLOCK();
	return got;
}

/* "key":value or "key":"value", as a string. */
static int ts_get(const char *line, const char *key, char *out, int outlen) {
	char pat[40];
	const char *p, *e;
	int n;
	snprintf(pat, sizeof(pat), "\"%s\"", key);
	if ((p = strstr(line, pat)) == NULL || (p = strchr(p + strlen(pat), ':')) == NULL)
		return 0;
	for (p++; *p == ' ' || *p == '\t'; p++)
		;
	if (*p == '"') {
		p++;
		if ((e = strchr(p, '"')) == NULL)
			return 0;
	} else {
		for (e = p; *e && *e != ',' && *e != '}' && *e != ' '; e++)
			;
	}
	n = (int)(e - p);
	if (n >= outlen)
		n = outlen - 1;
	memcpy(out, p, n);
	out[n] = '\0';
	return 1;
}

static int ts_get_int(const char *line, const char *key, int dflt) {
	char b[32];
	if (!ts_get(line, key, b, sizeof(b)) || b[0] == '\0')
		return dflt;
	return atoi(b);
}

static void ts_name(const char *line, char *out, int outlen) {
	char b[64];
	int i, o = 0;
	if (!ts_get(line, "name", b, sizeof(b)) || b[0] == '\0')
		strcpy(b, "pass");
	for (i = 0; b[i] && o < outlen - 1 && o < 48; i++)
		if (isalnum((unsigned char)b[i]) || b[i] == '-' || b[i] == '_')
			out[o++] = b[i];
	if (o == 0)
		out[o++] = 'p';
	out[o] = '\0';
}

static const char *ts_dir = ".";

static void ts_write(const char *name, cq_tscan_rec *r, char *files, int flen) {
	char path[2048];
	FILE *fp;
	int i, j;
	files[0] = '\0';
	snprintf(path, sizeof(path), "%s/%s.raw", ts_dir, name);
	if ((fp = fopen(path, "wb")) != NULL) {
		if (r->raw_dark_len > 0)
			fwrite(r->raw_dark, 1, r->raw_dark_len, fp);
		if (r->raw_lit_len > 0)
			fwrite(r->raw_lit, 1, r->raw_lit_len, fp);
		fclose(fp);
		snprintf(files + strlen(files), flen - strlen(files), "\"%s.raw\"", name);
	}
	if (r->spec != NULL) {
		snprintf(path, sizeof(path), "%s/%s.spec.csv", ts_dir, name);
		if ((fp = fopen(path, "w")) != NULL) {
			fprintf(fp, "reading");
			for (j = 0; j < r->nwav; j++)
				fprintf(fp, ",%.0f", XSPECT_WL(r->wl_short, r->wl_long, r->nwav, j));
			fprintf(fp, "\n");
			for (i = 0; i < r->ngot; i++) {
				fprintf(fp, "%d", i);
				for (j = 0; j < r->nwav; j++)
					fprintf(fp, ",%.6f", r->spec[i * r->nwav + j]);
				fprintf(fp, "\n");
			}
			fclose(fp);
			snprintf(files + strlen(files), flen - strlen(files), ",\"%s.spec.csv\"", name);
		}
	}
	if (r->rec_spec != NULL) {
		snprintf(path, sizeof(path), "%s/%s.rec.csv", ts_dir, name);
		if ((fp = fopen(path, "w")) != NULL) {
			fprintf(fp, "patch");
			for (j = 0; j < r->nwav; j++)
				fprintf(fp, ",%.0f", XSPECT_WL(r->wl_short, r->wl_long, r->nwav, j));
			fprintf(fp, "\n");
			for (i = 0; i < r->npatch; i++) {
				fprintf(fp, "%d", i);
				for (j = 0; j < r->nwav; j++)
					fprintf(fp, ",%.6f", r->rec_spec[i * r->nwav + j]);
				fprintf(fp, "\n");
			}
			fclose(fp);
			snprintf(files + strlen(files), flen - strlen(files), ",\"%s.rec.csv\"", name);
		}
	}
}

static void ts_emit_fired(const char *name, cq_tscan_rec *r, int rc) {
	char files[512], body[1600];
	FILE *fp;
	char path[2048];
	ts_write(name, r, files, sizeof(files));
#define REL(t) ((t) != 0 ? (int)((t) - r->t_fire) : -1)
	snprintf(body, sizeof(body),
	    "{\"event\":\"tscan_fired\",\"t\":%u,\"name\":\"%s\",\"ok\":%s,\"rc\":%d,"
	    "\"n\":%d,\"got\":%d,\"dark_ev\":%d,\"dark_check\":%d,\"lit_ev\":%d,\"misc_ev\":%d,"
	    "\"dark_sent\":%d,\"lit_sent\":%d,"
	    "\"t_fire\":%u,\"ms_dark_trig\":%d,\"ms_dark_data\":%d,\"ms_lit_trig\":%d,"
	    "\"ms_lit_data\":%d,\"ms_misc\":%d,\"since_lamp_off_ms\":%u,\"since_lights_off_ms\":%u,"
	    "\"misc\":[%d,%d,%d,%d,%d],\"maxraw\":%d,\"saturated\":%d,"
	    "\"nwav\":%d,\"wl\":[%.1f,%.1f],\"patches\":%d,\"rec_ev\":%d,\"files\":[%s]}",
	    msec_time(), name, rc == 0 ? "true" : "false", rc, r->nread, r->ngot,
	    r->dark_ev, r->dark_proc_ev, r->lit_ev, r->misc_ev, r->dark_sent, r->lit_sent,
	    r->t_fire, REL(r->t_dark_trig), REL(r->t_dark_data), REL(r->t_lit_trig),
	    REL(r->t_lit_data), REL(r->t_misc), r->since_lamp_off_ms, r->since_lights_off_ms,
	    r->misc[0], r->misc[1], r->misc[2], r->misc[3], r->misc[4], r->maxraw, r->saturated,
	    r->nwav, r->wl_short, r->wl_long, r->npatch, r->rec_ev, files);
#undef REL
	snprintf(path, sizeof(path), "%s/%s.json", ts_dir, name);
	if ((fp = fopen(path, "w")) != NULL) {
		fprintf(fp, "%s\n", body);
		fclose(fp);
	}
	cq_emit_raw("%s", body);
}

/* The instrument path: the first i1Pro 2 in the list (or the -c port, if it is
 * one). The table itself is never opened here. */
static icompath *ts_path(icompaths *icmps, int comport) {
	icompath *ip;
	int i;
	if (icmps == NULL)
		return NULL;
	if (comport > 0 && (ip = icmps->get_path(icmps, comport)) != NULL
	 && ip->dtype == instI1Pro2)
		return ip;
	for (i = 0; i < icmps->npaths; i++)
		if (icmps->paths[i] != NULL && icmps->paths[i]->dtype == instI1Pro2)
			return icmps->paths[i];
	return NULL;
}

int cq_run_table_scan(int comport, flow_control fc, const char *outdir,
                      void (*guard)(inst *it)) {
	icompaths *icmps = NULL;
	icompath *ipath = NULL;
	inst *it = NULL;
	inst_code rv;
	char line[256], name[64];
	int calibrated = 0;

	if (!cq_json) {
		fprintf(stderr, "--i1io-table-scan needs --json\n");
		return 1;
	}
	if (cq_i1pro2_lights || cq_ruler) {
		cq_emit_error("tscan_options", "--i1io-table-scan cannot be combined with the lights or ruler options");
		return 1;
	}
	ts_dir = outdir;
#ifdef NT
	if (!cq_ts_lock_init) { InitializeCriticalSection(&cq_ts_lock); cq_ts_lock_init = 1; }
#endif
	cq_tscan_line_hook = cq_ts_push;
	cq_emit_raw("{\"event\":\"tscan_start\",\"t\":%u,\"build\":\"%s\"}", msec_time(),
	            cq_helper_build_string());

	if ((icmps = new_icompaths(g_log)) != NULL)
		ipath = ts_path(icmps, comport);
	if (ipath == NULL) {
		cq_emit_error("no_instrument", "no X-Rite i1Pro 2 found");
		if (icmps != NULL)
			icmps->del(icmps);
		return 1;
	}
	inst_reset_uih();
	it = new_inst(ipath, 0, g_log, cq_uicallback, inst_get_uicontext());
	if (it == NULL) {
		cq_emit_error("no_instrument", "");
		icmps->del(icmps);
		return 1;
	}
	if (guard != NULL)
		guard(it);	/* always let the instrument go, as every reading does */
	if ((rv = it->init_coms(it, baud_38400, fc, 15.0)) != inst_ok
	 || (rv = it->init_inst(it)) != inst_ok) {
		cq_emit_error("no_instrument", it->interp_error(it, rv));
		it->del(it);
		icmps->del(icmps);
		return 1;
	}
	cq_exit_guard_signals();
	if (it->get_itype(it) != instI1Pro2) {
		cq_emit_error("tscan_instrument", "not an i1Pro 2");
		it->del(it);
		icmps->del(icmps);
		return 1;
	}
	if ((rv = it->set_mode(it, inst_mode_ref_strip | inst_mode_spectral)) != inst_ok) {
		cq_emit_error("tscan_mode", it->interp_error(it, rv));
		it->del(it);
		icmps->del(icmps);
		return 1;
	}
	cq_emit_raw("{\"event\":\"tscan_instrument\",\"t\":%u,\"model\":\"%s\"}",
	            msec_time(), inst_name(it->get_itype(it)));

	for (;;) {
		if (!cq_ts_take(line, sizeof(line))) {
			if (cq_stdin_eof)
				break;
			msec_sleep(1);		/* a fire is acted on within about 1 ms */
			continue;
		}
		if (strstr(line, "\"tscan_fire\"") != NULL) {
			int n = ts_get_int(line, "n", 0);
			int np = ts_get_int(line, "patches", 0);
			cq_tscan_rec r;
			int rc;
			ts_name(line, name, sizeof(name));
			cq_emit_raw("{\"event\":\"tscan_firing\",\"t\":%u,\"name\":\"%s\",\"n\":%d}",
			            msec_time(), name, n);
			rc = i1pro2_cq_tscan_fire((void *)it, n, np, &r);
			ts_emit_fired(name, &r, rc);
			cq_tscan_rec_clear(&r);
		} else if (strstr(line, "\"tscan_arm\"") != NULL) {
			int n = ts_get_int(line, "n", 0);
			int wmax = ts_get_int(line, "wait_ms", 3000);
			int w = 0, rdy, waited = 0;
			char why[96];
			unsigned int t0 = msec_time();
			if (wmax < 0) wmax = 0;
			if (wmax > 10000) wmax = 10000;
			for (;;) {
				why[0] = '\0';
				rdy = i1pro2_cq_tscan_ready((void *)it, n, &w, why, sizeof(why));
				if (rdy != 0 || (int)(msec_time() - t0) + w > wmax)
					break;
				msec_sleep(w > 20 ? 20 : (w > 0 ? w : 1));
				waited = 1;
			}
			cq_emit_raw("{\"event\":\"tscan_armed\",\"t\":%u,\"n\":%d,\"ready\":%s,"
			            "\"waited_ms\":%u,\"still_ms\":%d,\"why\":\"%s\"}", msec_time(), n,
			            rdy == 1 ? "true" : "false", msec_time() - t0,
			            rdy == 1 ? 0 : w, rdy == -1 ? why : (rdy == 0 ? "timing" : ""));
			(void)waited;
		} else if (strstr(line, "\"tscan_lights_off\"") != NULL) {
			int e = i1pro2_cq_tscan_lights_off((void *)it);
			cq_emit_raw("{\"event\":\"tscan_lights_off\",\"t\":%u,\"err\":%d}", msec_time(), e);
		} else if (strstr(line, "\"tscan_calibrate\"") != NULL) {
			rv = cq_handle_calibrate(it, inst_calt_needed, inst_calc_none, 0);
			calibrated = (rv & inst_mask) == inst_ok;
			cq_emit_raw("{\"event\":\"tscan_calibrated\",\"t\":%u,\"ok\":%s,\"detail\":\"%s\"}",
			            msec_time(), calibrated ? "true" : "false",
			            calibrated ? "" : "calibration failed or cancelled");
		} else if (strstr(line, "\"tscan_quit\"") != NULL) {
			break;
		} else {
			cq_emit_raw("{\"event\":\"tscan_unknown\",\"t\":%u}", msec_time());
		}
	}
	cq_tscan_line_hook = NULL;
	cq_emit_raw("{\"event\":\"tscan_end\",\"t\":%u}", msec_time());
	it->del(it);
	icmps->del(icmps);
	return 0;
}
