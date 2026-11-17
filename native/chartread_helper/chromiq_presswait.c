/* chromiq_presswait.c: the instrument's button as "Aimed" while ChromIQ drives
 * an X-Rite i1iO 2 table (round B of the table drive, 2026-11-17).
 *
 *   chromiq-chartread --json --i1io-press-wait [-c <port>]
 *
 * Without --i1io-press-wait nothing in this file runs, and the helper's other
 * modes are unchanged (tests/test_i1io_press_wait.py).
 *
 * WHAT IT DOES: it opens the i1Pro 2 exactly as every reading does (new_inst,
 * init_coms, init_inst; with the replay instrument in tests), takes nothing
 * from it but its button, and tells the app when the button was pressed while
 * the app had ARMED it. It takes NO reading, sets no measuring mode, switches
 * no lamp, sends nothing to the table (this process never opens the table:
 * the table belongs to the app's own USB connection) and writes nothing.
 *
 * WHY THAT HAS NO SIDE EFFECT ON THE INSTRUMENT (read in the vendored driver,
 * native/instlib/i1pro_imp.c): the i1Pro driver starts its switch thread in
 * i1pro_imp_init (line ~560) whatever the program wants; the thread reads one
 * byte from the switch endpoint 0x84 (i1pro_waitfor_switch_th, ~11996) and, on
 * a press, only counts it (switch_count) and calls the event callback
 * (~11193). A press starts a measurement only inside i1pro_imp_measure with the
 * trigger inst_opt_trig_user_switch, which hides the press from the callback
 * (hide_switch, ~2998): this mode never measures, so a press here is reported
 * and nothing else. Opening the instrument is what any hand reading does
 * (reset, EEPROM read, the stored calibration restored, high power); on a Mac
 * ArgyllCMS closes X-Rite's i1ProDeviceService then, as for any reading.
 * Preferences' "Try it" (--button-test) has opened instruments this way since
 * 4.3.13 on real i1Pro and ColorMunki hands.
 *
 * Commands (one JSON object per line; the command thread hands every
 * "press_*" command here, see chromiq_json.c):
 *   {"cmd":"press_arm","id":"<token>","wait_ms":"<ms>","min_ms":"<ms>"}
 *       report the NEXT press as {"event":"press","id":"<token>"} and disarm.
 *       wait_ms (clamped 1000..900000, default 600000): after that long
 *       without a press, {"event":"press_timeout","id":...} and disarm.
 *       min_ms (clamped 0..3000, default 400): a press sooner than that after
 *       the arm is not taken as the answer (the person may have pressed for
 *       the question before): {"event":"press_ignored","why":"too_soon"}.
 *   {"cmd":"press_disarm"}   {"event":"press_disarmed","id":...} (a cancel)
 *   {"cmd":"press_quit"}, {"cmd":"quit"} or the end of stdin: the instrument is
 *       let go (it->del), then {"event":"press_wait_end"}.
 * A press while nothing is armed: {"event":"press_ignored","why":"not_armed"}.
 * Every event carries "t", this process's msec clock.
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

#define PW_Q 8
static char pw_q[PW_Q][256];
static volatile int pw_head = 0, pw_tail = 0;
/* presses counted by the driver's switch thread, taken by the main loop */
static volatile int pw_presses = 0;
#ifdef NT
static CRITICAL_SECTION pw_lock;
static int pw_lock_init = 0;
#define PW_LOCK()   EnterCriticalSection(&pw_lock)
#define PW_UNLOCK() LeaveCriticalSection(&pw_lock)
#else
static pthread_mutex_t pw_lock = PTHREAD_MUTEX_INITIALIZER;
#define PW_LOCK()   pthread_mutex_lock(&pw_lock)
#define PW_UNLOCK() pthread_mutex_unlock(&pw_lock)
#endif

/* The command thread, for every "press_*" command. A full queue drops the
 * line; the app re-arms per question, and a dropped arm only means the button
 * is not taken for that mark (the panel's Aimed always works). */
static void pw_push(const char *line) {
	int next;
	PW_LOCK();
	next = (pw_head + 1) % PW_Q;
	if (next != pw_tail) {
		strncpy(pw_q[pw_head], line, sizeof(pw_q[0]) - 1);
		pw_q[pw_head][sizeof(pw_q[0]) - 1] = '\0';
		pw_head = next;
	}
	PW_UNLOCK();
}

static int pw_take(char *out, int size) {
	int got = 0;
	PW_LOCK();
	if (pw_head != pw_tail) {
		strncpy(out, pw_q[pw_tail], size - 1);
		out[size - 1] = '\0';
		pw_tail = (pw_tail + 1) % PW_Q;
		got = 1;
	}
	PW_UNLOCK();
	return got;
}

/* The driver's switch thread (or the replay's {"cmd":"switch"}): count only.
 * Nothing is emitted from that thread and nothing reaches the instrument. */
static void pw_event(void *cntx, inst_event_type event) {
	(void)cntx;
	if (event != inst_event_switch)
		return;
	PW_LOCK();
	pw_presses++;
	PW_UNLOCK();
}

static int pw_take_presses(void) {
	int n;
	PW_LOCK();
	n = pw_presses;
	pw_presses = 0;
	PW_UNLOCK();
	return n;
}

/* "key":"value" or "key":value, as a string */
static int pw_get(const char *line, const char *key, char *out, int outlen) {
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

static int pw_get_int(const char *line, const char *key, int dflt, int lo, int hi) {
	char b[32];
	int v;
	if (!pw_get(line, key, b, sizeof(b)) || b[0] == '\0')
		return dflt;
	v = atoi(b);
	return v < lo ? lo : (v > hi ? hi : v);
}

/* the token, as letters, digits, '-' and '_' only (it is echoed into JSON) */
static void pw_token(const char *line, char *out, int outlen) {
	char b[64];
	int i, o = 0;
	out[0] = '\0';
	if (!pw_get(line, "id", b, sizeof(b)))
		return;
	for (i = 0; b[i] && o < outlen - 1 && o < 40; i++)
		if (isalnum((unsigned char)b[i]) || b[i] == '-' || b[i] == '_')
			out[o++] = b[i];
	out[o] = '\0';
}

int cq_run_press_wait(int comport, flow_control fc, void (*guard)(inst *it)) {
	icompaths *icmps = NULL;
	icompath *ipath = NULL;
	inst *it = NULL;
	inst_code rv;
	char line[256], armed_id[48] = "";
	int armed = 0, n, i;
	unsigned int t_arm = 0, wait_ms = 0, min_ms = 0;

	if (!cq_json) {
		fprintf(stderr, "--i1io-press-wait needs --json\n");
		return 1;
	}
	if (cq_i1pro2_lights || cq_ruler) {
		cq_emit_error("press_options", "--i1io-press-wait cannot be combined with the lights or ruler options");
		return 1;
	}
#ifdef NT
	if (!pw_lock_init) { InitializeCriticalSection(&pw_lock); pw_lock_init = 1; }
#endif
	/* set before the instrument opens: an arm sent meanwhile waits in the queue */
	cq_presswait_line_hook = pw_push;
	cq_emit_raw("{\"event\":\"press_wait_start\",\"t\":%u,\"build\":\"%s\"}", msec_time(),
	            cq_helper_build_string());

	if (cq_replay_active()) {
		inst_reset_uih();
		it = cq_new_replay_inst(g_log, cq_uicallback, inst_get_uicontext());
	} else {
		if ((icmps = new_icompaths(g_log)) != NULL) {
			if (comport > 0 && (ipath = icmps->get_path(icmps, comport)) != NULL
			 && ipath->dtype != instI1Pro2)
				ipath = NULL;
			for (i = 0; ipath == NULL && i < icmps->npaths; i++)
				if (icmps->paths[i] != NULL && icmps->paths[i]->dtype == instI1Pro2)
					ipath = icmps->paths[i];
		}
		if (ipath != NULL) {
			inst_reset_uih();
			it = new_inst(ipath, 0, g_log, cq_uicallback, inst_get_uicontext());
		}
	}
	if (it == NULL) {
		cq_presswait_line_hook = NULL;
		cq_emit_error("no_instrument", "no X-Rite i1Pro 2 found");
		if (icmps != NULL)
			icmps->del(icmps);
		return 1;
	}
	if (guard != NULL)
		guard(it);	/* always let the instrument go, as every reading does */
	it->set_event_callback(it, pw_event, (void *)it);
	if ((rv = it->init_coms(it, baud_38400, fc, 15.0)) != inst_ok
	 || (rv = it->init_inst(it)) != inst_ok) {
		cq_presswait_line_hook = NULL;
		cq_emit_error("no_instrument", it->interp_error(it, rv));
		it->del(it);
		if (icmps != NULL)
			icmps->del(icmps);
		return 1;
	}
	cq_exit_guard_signals();
	if (it->get_itype(it) != instI1Pro2) {
		cq_presswait_line_hook = NULL;
		cq_emit_error("press_instrument", "not an i1Pro 2");
		it->del(it);
		if (icmps != NULL)
			icmps->del(icmps);
		return 1;
	}
	pw_take_presses();	/* a press from before the instrument was open is nobody's answer */
	cq_emit_raw("{\"event\":\"press_wait_ready\",\"t\":%u,\"model\":\"%s\"}", msec_time(),
	            inst_name(it->get_itype(it)));

	for (;;) {
		int k = cq_poll_char();
		if (k == 0x1b || k == 0x03 || cq_stdin_eof)
			break;
		n = pw_take_presses();
		for (i = 0; i < n; i++) {
			unsigned int now = msec_time();
			if (!armed) {
				cq_emit_raw("{\"event\":\"press_ignored\",\"t\":%u,\"why\":\"not_armed\"}", now);
			} else if (now - t_arm < min_ms) {
				cq_emit_raw("{\"event\":\"press_ignored\",\"t\":%u,\"why\":\"too_soon\","
				            "\"id\":\"%s\",\"after_ms\":%u}", now, armed_id, now - t_arm);
			} else {
				armed = 0;
				cq_emit_raw("{\"event\":\"press\",\"t\":%u,\"id\":\"%s\",\"after_ms\":%u}",
				            now, armed_id, now - t_arm);
			}
		}
		if (armed && msec_time() - t_arm >= wait_ms) {
			armed = 0;
			cq_emit_raw("{\"event\":\"press_timeout\",\"t\":%u,\"id\":\"%s\"}", msec_time(),
			            armed_id);
		}
		if (!pw_take(line, sizeof(line))) {
			msec_sleep(5);
			continue;
		}
		if (strstr(line, "\"press_arm\"") != NULL) {
			pw_token(line, armed_id, sizeof(armed_id));
			wait_ms = (unsigned int)pw_get_int(line, "wait_ms", 600000, 1000, 900000);
			min_ms = (unsigned int)pw_get_int(line, "min_ms", 400, 0, 3000);
			pw_take_presses();	/* only a press after the arm answers it */
			t_arm = msec_time();
			armed = 1;
			cq_emit_raw("{\"event\":\"press_armed\",\"t\":%u,\"id\":\"%s\",\"wait_ms\":%u,"
			            "\"min_ms\":%u}", t_arm, armed_id, wait_ms, min_ms);
		} else if (strstr(line, "\"press_disarm\"") != NULL) {
			cq_emit_raw("{\"event\":\"press_disarmed\",\"t\":%u,\"id\":\"%s\",\"was_armed\":%s}",
			            msec_time(), armed_id, armed ? "true" : "false");
			armed = 0;
		} else if (strstr(line, "\"press_quit\"") != NULL) {
			break;
		} else {
			cq_emit_raw("{\"event\":\"press_unknown\",\"t\":%u}", msec_time());
		}
	}
	cq_presswait_line_hook = NULL;
	it->set_event_callback(it, NULL, NULL);
	/* said before the close: a close that blocks is ended by the exit guard */
	cq_emit_raw("{\"event\":\"press_wait_end\",\"t\":%u}", msec_time());
	it->del(it);
	if (icmps != NULL)
		icmps->del(icmps);
	return 0;
}
