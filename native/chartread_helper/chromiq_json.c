/* JSON event emission + stdin command channel for chromiq-chartread.
 * AGPL-3.0 — see ../instlib/License.txt. Part of ChromIQ issue #126. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef NT
# include <windows.h>
# include <process.h>
#else
# include <pthread.h>
# include <time.h>
#endif
#ifdef __linux__
# include <errno.h>
# include <unistd.h>
#endif

#include "chromiq_ext.h"

int cq_json = 0;
int cq_autosave = 0;
int cq_safenet = 0;
int cq_xychart = 0;

/* ------------------------------------------------------------------ */
/* Emission: every event is one complete JSON object on one line,      */
/* flushed immediately so the GUI never waits on buffering.            */

void cq_emit_raw(const char *fmt, ...) {
	va_list args;
	if (!cq_json)
		return;
	/* chartread's prompts often end without a newline — start every JSON
	 * object at column 0 so the GUI's line decoder always sees it clean.
	 * #202: held under stdout's lock so a line from another thread (the
	 * driver's scan_ready) can never be written into the middle of it. */
	cq_out_lock();
	fputc('\n', stdout);
	va_start(args, fmt);
	vfprintf(stdout, fmt, args);
	va_end(args);
	fputc('\n', stdout);
	fflush(stdout);
	cq_out_unlock();
}

void cq_emit_simple(const char *event) {
	cq_emit_raw("{\"event\":\"%s\"}", event);
}

void cq_emit_error(const char *kind, const char *detail) {
	char esc[512];
	cq_json_escape(esc, sizeof(esc), detail != NULL ? detail : "");
	cq_emit_raw("{\"event\":\"error\",\"kind\":\"%s\",\"detail\":\"%s\"}", kind, esc);
}

/* Kept in the binary so the packaging test can see which build it is. `used`
 * stops the compiler discarding a variable nothing reads; the volatile pointer
 * is the portable fallback for toolchains without the attribute. */
#if defined(__GNUC__) || defined(__clang__)
__attribute__((used))
#endif
static const char cq_helper_build[] = CQ_HELPER_BUILD;
const char *cq_helper_build_string(void) { return cq_helper_build; }

void cq_json_escape(char *dst, size_t dstlen, const char *src) {
	size_t o = 0;
	for (; *src != '\0' && o + 6 < dstlen; src++) {
		unsigned char c = (unsigned char)*src;
		if (c == '"' || c == '\\') {
			dst[o++] = '\\';
			dst[o++] = (char)c;
		} else if (c < 0x20) {
			o += (size_t)snprintf(dst + o, dstlen - o, "\\u%04x", c);
		} else {
			dst[o++] = (char)c;
		}
	}
	dst[o] = '\0';
}

/* ------------------------------------------------------------------ */
/* Command channel: a background thread reads stdin lines and parses   */
/* the tiny fixed command set. Commands map onto the key codes the     */
/* console path uses, taken by the ui-callback poll via                */
/* cq_cmd_take_key() — the exact spot console keys are consumed today. */

static volatile int   cq_pending_key = CQ_KEY_NONE;
static char           cq_goto_label[16];
static char           cq_file_as_label[16];  /* {"cmd":"file_as"}'s "as" */
static int            cq_file_as_keep;       /* ...its "earlier":"keep" (2026-10-21) */

/* CHROMIQ_EXT: the calibration the user asked for -- see the "calibrate"
 * command in cq_handle_line for why these are not the key slot. */
static volatile int   cq_cal_requested = 0;  /* {"cmd":"calibrate"} arrived  */
static volatile int   cq_cal_gate = 0;       /* strip/patch loop is waiting  */
static volatile int   cq_cal_in_request = 0; /* a requested cal is prompting */
static volatile int   cq_cal_cancel = 0;     /* {"cmd":"cal_cancel"} for it  */

/* CHROMIQ_EXT (B1, Basti 2026-10-21): the instrument's button as Retry.
 * Open ONLY while the strip loop waits at the misread prompt ("Strip Read
 * Failed"); cq_event_callback reports a press as {"event":"switch"} only
 * while it is open. The engine never acts on the press itself: the GUI
 * decides, through the same path as its Retry button. */
static volatile int   cq_switch_gate = 0;

/* CHROMIQ_EXT (jctay 149802, Basti 2026-10-23): the pause between pages.
 * The strip the GUI asked the engine to hold after ({"cmd":"hold_after"}),
 * empty for none. Cleared at every strip_ready (cq_hold_clear), so it is
 * only ever about the strip just offered. */
static char           cq_hold_strip[16] = "";

/* CHROMIQ_EXT #159: the external-values line channel.
 *
 * -x mode reads a whole LINE from stdin (a measurement, or a one-letter
 * navigation command), but in JSON mode stdin belongs to this command reader,
 * so that read can never succeed: it returns immediately, the loop `continue`s
 * and spins, emitting spot_ready without bound. -x and --json were therefore
 * mutually exclusive, which made a non-Argyll instrument backend impossible.
 *
 * This gives -x its own line queue, fed by JSON commands, so the existing
 * parser in the read loop is reached unchanged -- it still sees a line and
 * still decides for itself whether it is a value or a command. */
#define CQ_LINE_Q  16
static char           cq_line_q[CQ_LINE_Q][128];
static volatile int   cq_line_head = 0, cq_line_tail = 0;
static volatile int   cq_line_dropped = 0;

/* True when a line is waiting to be consumed. */
static int cq_line_ready_locked(void) { return cq_line_head != cq_line_tail; }

/* Append one line. A REAL QUEUE, not a single slot: the first version kept one
 * buffer and overwrote it, so two commands arriving before the read loop woke
 * up silently destroyed the first. Measured: {"cmd":"goto","patch":"B1"}
 * followed by a value recorded that value against A1 -- the user clicks B1 and
 * B1's colour lands in A1, with no event and no error. Wrong colour written
 * into a .ti3 with no trace is the worst failure this file can produce, so
 * ordering is preserved and an overflow is COUNTED rather than ignored. */
static void cq_line_push(const char *line) {
	int next = (cq_line_head + 1) % CQ_LINE_Q;
	if (next == cq_line_tail) {      /* full: never silently overwrite */
		cq_line_dropped++;
		return;
	}
	strncpy(cq_line_q[cq_line_head], line, sizeof(cq_line_q[0]) - 1);
	cq_line_q[cq_line_head][sizeof(cq_line_q[0]) - 1] = '\0';
	cq_line_head = next;
}
#ifdef NT
static CRITICAL_SECTION cq_lock;
#else
static pthread_mutex_t cq_lock = PTHREAD_MUTEX_INITIALIZER;
#endif

static void cq_lock_take(void) {
#ifdef NT
	EnterCriticalSection(&cq_lock);
#else
	pthread_mutex_lock(&cq_lock);
#endif
}

static void cq_lock_give(void) {
#ifdef NT
	LeaveCriticalSection(&cq_lock);
#else
	pthread_mutex_unlock(&cq_lock);
#endif
}

/* Extract a string value for `key` out of a one-line JSON command.
 * Deliberately minimal: our own GUI is the only writer on this pipe. */
static int cq_json_get(const char *line, const char *key, char *out, size_t outlen) {
	char pat[48];
	const char *p, *e;
	size_t n;
	snprintf(pat, sizeof(pat), "\"%s\"", key);
	if ((p = strstr(line, pat)) == NULL)
		return 0;
	if ((p = strchr(p + strlen(pat), ':')) == NULL)
		return 0;
	while (*p == ':' || *p == ' ' || *p == '\t')
		p++;
	if (*p != '"')
		return 0;
	p++;
	if ((e = strchr(p, '"')) == NULL)
		return 0;
	n = (size_t)(e - p);
	if (n >= outlen)
		n = outlen - 1;
	memcpy(out, p, n);
	out[n] = '\0';
	return 1;
}

static void cq_handle_line(const char *line) {
	char cmd[24];
	int key = CQ_KEY_NONE;
	char gl[16] = "";

	if (!cq_json_get(line, "cmd", cmd, sizeof(cmd)))
		return;

	if (strcmp(cmd, "swipe") == 0) {
		/* Replay only: trigger reading the armed strip, with optional
		 * overrides. Ignored (harmless) with a real instrument. */
		char rev[8] = "";
		cq_lock_take();
		if (!cq_json_get(line, "as", cq_swipe_as, sizeof(cq_swipe_as)))
			cq_swipe_as[0] = '\0';
		if (!cq_json_get(line, "fault", cq_swipe_fault, sizeof(cq_swipe_fault)))
			cq_swipe_fault[0] = '\0';
		/* B1: "reason" is the driver's sentence a misread reports, e.g.
		 * "Too many patches", so the GUI's per-error advice is testable. */
		if (!cq_json_get(line, "reason", cq_swipe_reason, sizeof(cq_swipe_reason)))
			cq_swipe_reason[0] = '\0';
		cq_swipe_reversed = 0;
		/* "reversed":true is a bare token — cq_json_get only reads strings,
		 * so probe for the raw text. */
		if (strstr(line, "\"reversed\"") != NULL && strstr(line, "true") != NULL)
			cq_swipe_reversed = 1;
		(void)rev;
		cq_swipe_pending = 1;
		cq_lock_give();
		return;
	}

	if (strcmp(cmd, "switch") == 0) {
		/* B1, replay only: the instrument's button was pressed, as the
		 * driver's switch thread reports it -- a trigger while the strip is
		 * armed, otherwise an inst_event_switch. Ignored with a real
		 * instrument (cq_replay_switch_press does nothing then). */
		cq_replay_switch_press();
		return;
	}

	if (strcmp(cmd, "gesture_wait") == 0) {
		/* Button gestures: a new wait for further presses, e.g. while
		 * Preferences' "Try it" runs and the box is changed. Only once
		 * gestures were switched on with --gestures; clamped as there. */
		char ms[16] = "";
		if (cq_gesture_ms > 0 && cq_json_get(line, "ms", ms, sizeof(ms))) {
			int v = atoi(ms);
			if (v < 200) v = 200;
			if (v > 2000) v = 2000;
			cq_lock_take();
			cq_gesture_ms = v;
			cq_lock_give();
		}
		return;
	}

	if (strcmp(cmd, "presses") == 0) {
		/* Replay only: a group of presses at the given times (ms after
		 * now). Ignored with a real instrument (cq_replay_presses checks). */
		char at[96] = "";
		if (cq_json_get(line, "at_ms", at, sizeof(at)))
			cq_replay_presses(at);
		return;
	}

	if (strcmp(cmd, "hold_after") == 0) {
		/* The pause between pages: hold after this strip is accepted.
		 * Not a key, so no prompt can ever read it as an answer. */
		char st[16] = "";
		if (!cq_json_get(line, "strip", st, sizeof(st)))
			return;
		cq_lock_take();
		strncpy(cq_hold_strip, st, sizeof(cq_hold_strip) - 1);
		cq_hold_strip[sizeof(cq_hold_strip) - 1] = '\0';
		cq_lock_give();
		return;
	}

	if (strcmp(cmd, "trigger") == 0) {
		/* #202, replay only: the instrument's button was pressed. Optional
		 * "ready_ms":"<n>" sets the delay to the ready-to-scan moment.
		 * Ignored (harmless) with a real instrument. */
		char ms[16] = "";
		cq_lock_take();
		cq_trigger_ready_ms = 700;
		if (cq_json_get(line, "ready_ms", ms, sizeof(ms)) && atoi(ms) >= 0)
			cq_trigger_ready_ms = atoi(ms);
		cq_trigger_pending = 1;
		cq_lock_give();
		return;
	}

	/* "goto" carries a target label: "strip" in strip mode, "patch" in
	 * spot mode. Both feed the same CQ_KEY_GOTO / cq_goto_label channel —
	 * the read loop matches the label against its own units. */
	/* {"cmd":"value","xyz":"95.1 100.0 108.8"} -- one external measurement.
	 * The payload is passed through VERBATIM to -x's own parser; we never
	 * interpret the numbers here, so the units and count stay whatever that
	 * parser already accepts (XYZ with -x, L*a*b* with -xl). */
	if (strcmp(cmd, "value") == 0) {
		char v[sizeof(cq_line_q[0])] = "";
		if (!cq_json_get(line, "xyz", v, sizeof(v))
		 && !cq_json_get(line, "lab", v, sizeof(v))
		 && !cq_json_get(line, "value", v, sizeof(v)))
			return;                    /* no payload -> ignore, never queue */
		cq_lock_take();
		cq_line_push(v);
		cq_lock_give();
		return;
	}

	/* CHROMIQ_EXT: a calibration the USER asked for (K, or the Calibrate
	 * button). It is NOT a key, on purpose (challenge 1a):
	 *  * the single key slot is consumed by whatever reads next, and a
	 *    prompt opened by a strip that was still being swiped would take
	 *    it -- at the wrong-strip warning "any other key = retry" throws a
	 *    good reading away;
	 *  * a key is mirrored onto the -x line queue, and a 'k' line reaching
	 *    the patch loop under -x dereferences a NULL instrument.
	 * So it is a flag of its own, turned into a 'k' command only by
	 * cq_uicallback, only at inst_armed, and only while the strip or patch
	 * loop has opened the gate (cq_cal_gate_set). Nothing else reads it. */
	if (strcmp(cmd, "calibrate") == 0) {
		cq_lock_take();
		cq_cal_requested = 1;
		cq_lock_give();
		return;
	}
	/* ...and its Cancel, honoured only while such a calibration is asking
	 * for the instrument to be placed. Anywhere else it is ignored, so a
	 * late cancel can never become a strip abort. */
	if (strcmp(cmd, "cal_cancel") == 0) {
		cq_lock_take();
		if (cq_cal_in_request)
			cq_cal_cancel = 1;
		cq_lock_give();
		return;
	}

	/* CHROMIQ_EXT (Knut #182 6102031563): "I read strip B". The reading
	 * the engine filed under "strip" is "as"'s: the strip loop moves it
	 * there (cq_take_goto() carries "strip", cq_take_file_as() "as"). */
	char ga[16] = "";
	char ge[8] = "";
	if (strcmp(cmd, "file_as") == 0
	 && cq_json_get(line, "strip", gl, sizeof(gl))
	 && cq_json_get(line, "as", ga, sizeof(ga)))
		key = CQ_KEY_FILE_AS;
	else if (strcmp(cmd, "goto") == 0
	 && (cq_json_get(line, "strip", gl, sizeof(gl))
	  || cq_json_get(line, "patch", gl, sizeof(gl))))
		key = CQ_KEY_GOTO;
	else if (strcmp(cmd, "resume") == 0)
		key = CQ_KEY_RESUME;           /* only the hold acts on it */
	else if (strcmp(cmd, "hold") == 0)
		key = CQ_KEY_HOLD;             /* only an armed strip acts on it */
	else if (strcmp(cmd, "next_unread") == 0)
		key = 'n';
	else if (strcmp(cmd, "forward") == 0)
		key = 'f';
	else if (strcmp(cmd, "back") == 0)
		key = 'b';
	else if (strcmp(cmd, "read") == 0)
		key = 0x0d;                    /* spot-mode read trigger (== Return) */
	else if (strcmp(cmd, "done") == 0 || strcmp(cmd, "save") == 0)
		key = 'd';
	else if (strcmp(cmd, "retry") == 0)
		key = 'r';                     /* "any other key" — never Return */
	else if (strcmp(cmd, "accept") == 0 || strcmp(cmd, "ok") == 0)
		key = 0x0d;                    /* Return — same as console */
	else if (strcmp(cmd, "yes") == 0)
		key = 'y';
	else if (strcmp(cmd, "no") == 0)
		key = 'n';
	else if (strcmp(cmd, "skip") == 0)
		key = 's';                     /* optional-calibration skip */
	else if (strcmp(cmd, "quit") == 0)
		key = 0x1b;                    /* Esc */
	else
		return;                        /* unknown commands are ignored */

	cq_lock_take();
	cq_pending_key = key;
	if (key == CQ_KEY_GOTO || key == CQ_KEY_FILE_AS) {
		strncpy(cq_goto_label, gl, sizeof(cq_goto_label) - 1);
		cq_goto_label[sizeof(cq_goto_label) - 1] = '\0';
	}
	if (key == CQ_KEY_FILE_AS) {
		strncpy(cq_file_as_label, ga, sizeof(cq_file_as_label) - 1);
		cq_file_as_label[sizeof(cq_file_as_label) - 1] = '\0';
		/* "earlier":"keep": the strip the reading came off gets back the
		 * reading it had before that swipe (Basti, 2026-10-21). */
		cq_file_as_keep = cq_json_get(line, "earlier", ge, sizeof(ge))
		                  && strcmp(ge, "keep") == 0;
	}
	/* Mirror the key onto the line channel so the SAME command works in -x,
	 * where the read loop wants a line rather than a key. -x's parser reads
	 * the first non-space character, so a one-character line is exactly what
	 * the console would have delivered. Without this, Stop/forward/back/done
	 * would be inert on the external-values path. */
	{
		char one[128];
		if (key == CQ_KEY_GOTO) {
			/* Just the key. The LABEL does not travel on this queue: the read
			 * loop takes it from cq_goto_target (chromiq_chartread.c, the
			 * `incflag == 4` branch), which cq_take_goto() feeds. Packing it
			 * into the line as "gB1" discarded it silently -- the goto then did
			 * nothing and the value that followed landed on whatever patch
			 * happened to be current. */
			one[0] = 'g';
			one[1] = '\0';
		} else if (key > 0 && key < 128) {
			one[0] = (char)key;
			one[1] = '\0';
		} else {
			one[0] = '\0';
		}
		/* Queued unconditionally and IN ORDER with values. The old
		 * `if (!cq_line_ready)` guard dropped a navigation command whenever a
		 * value was already waiting, which is how a goto could vanish. */
		if (one[0] != '\0')
			cq_line_push(one);
	}
	cq_lock_give();
}

#if defined(__linux__)
/* LINUX ONLY: RAW read(2), NOT fgets(stdin). This thread spends its life
 * blocked inside a read of stdin; through stdio that means HOLDING stdin's
 * FILE lock the whole time, and glibc's exit() takes every FILE's lock to
 * unbuffer it. So on Linux the helper deadlocked in exit() after every
 * session, saved or fatal, until its stdin was closed (first Linux CI run,
 * 2026-10-04: ~65 tests timed out waiting for it to end; with this reader,
 * none did). macOS and Windows keep the fgets reader below, unchanged.
 * Same line semantics as fgets: up to 255 bytes, newline included. */
static void *cq_reader(void *arg) {
	char line[256];
	size_t n = 0;
	char c;
	(void)arg;
	for (;;) {
		ssize_t r = read(0, &c, 1);
		if (r < 0 && errno == EINTR)
			continue;
		if (r <= 0)
			break;
		line[n++] = c;
		if (c == '\n' || n == sizeof(line) - 1) {
			line[n] = '\0';
			cq_handle_line(line);
			n = 0;
		}
	}
	if (n > 0) {
		line[n] = '\0';
		cq_handle_line(line);
	}
	cq_stdin_eof = 1;
	return NULL;
}
#else
#ifdef NT
static unsigned __stdcall cq_reader(void *arg) {
#else
static void *cq_reader(void *arg) {
#endif
	char line[256];
	(void)arg;
	while (fgets(line, sizeof(line), stdin) != NULL)
		cq_handle_line(line);
	cq_stdin_eof = 1;
#ifdef NT
	return 0;
#else
	return NULL;
#endif
}
#endif

void cq_cmd_start(void) {
#ifdef NT
	InitializeCriticalSection(&cq_lock);
	_beginthreadex(NULL, 0, cq_reader, NULL, 0, NULL);
#else
	pthread_t t;
	pthread_create(&t, NULL, cq_reader, NULL);
	pthread_detach(t);
#endif
}

int cq_cmd_take_key(void) {
	int k;
	cq_lock_take();
	k = cq_pending_key;
	cq_pending_key = CQ_KEY_NONE;
	cq_lock_give();
	return k;
}

/* Swipe descriptor lives here so the command thread and the replay
 * instrument share one definition. */
volatile int cq_trigger_pending = 0;
int cq_trigger_ready_ms = 700;
volatile int cq_swipe_pending = 0;
char cq_swipe_as[8]      = "";
int  cq_swipe_reversed   = 0;
char cq_swipe_fault[16]  = "";
char cq_swipe_reason[96] = "";

static void cq_sleep_ms(int ms) {
#ifdef NT
	Sleep(ms);
#else
	struct timespec ts;
	ts.tv_sec = ms / 1000;
	ts.tv_nsec = (long)(ms % 1000) * 1000000L;
	nanosleep(&ts, NULL);
#endif
}

/* Blocking prompt read for the fork's error/confirm prompts. In JSON mode
 * the console is off-limits (stdin carries commands), so this only ever
 * consumes the command queue. Non-JSON mode never calls this — the fork
 * keeps stock next_con_char() there. */
int cq_wait_char(void) {
	for (;;) {
		int k = cq_cmd_take_key();
		/* A resume means something only in the hold (cq_hold_wait); at
		 * any prompt it is dropped, never taken as "any other key". */
		if (k != CQ_KEY_NONE && k != CQ_KEY_GOTO && k != CQ_KEY_FILE_AS
		 && k != CQ_KEY_RESUME && k != CQ_KEY_HOLD)
			return k;
		cq_press_group_poll("prompt");	/* inert unless gestures + gate */
		cq_sleep_ms(20);
	}
}

/* Block until a line arrives on the -x channel. Mirrors cq_wait_char, which is
 * the key equivalent. Returns 1 and fills buf; never returns without a line, so
 * the caller cannot spin. */
int cq_wait_line(char *buf, int size) {
	for (;;) {
		int got = 0;
		cq_lock_take();
		if (cq_line_ready_locked()) {
			strncpy(buf, cq_line_q[cq_line_tail], (size_t)size - 1);
			buf[size - 1] = '\0';
			cq_line_tail = (cq_line_tail + 1) % CQ_LINE_Q;
			cq_pending_key = CQ_KEY_NONE;   /* consumed as a line, not a key */
			got = 1;
		}
		cq_lock_give();
		if (got)
			return 1;
		cq_sleep_ms(20);
	}
}

/* How many lines were refused because the queue was full. Non-zero means the
 * host sent faster than the read loop consumed, which the protocol forbids
 * (wait for spot_ready before each value) -- surfaced so it can never be a
 * silent loss. */
int cq_line_overflow_count(void) {
	int n;
	cq_lock_take();
	n = cq_line_dropped;
	cq_lock_give();
	return n;
}

const char *cq_take_goto(void) {
	return cq_goto_label;
}

const char *cq_take_file_as(void) {
	return cq_file_as_label;
}

int cq_take_file_as_keep(void) {
	return cq_file_as_keep;
}

/* ------------------------------------------------------------------ */
/* CHROMIQ_EXT: the calibration the user asks for during a measurement. */

void cq_cal_gate_set(int on) {
	cq_lock_take();
	cq_cal_gate = on ? 1 : 0;
	cq_lock_give();
}

/* B1: the misread prompt's gate for the instrument's button. */
void cq_switch_gate_set(int on) {
	/* Gestures: a group never runs across a gate opening or closing, so
	 * presses from before the wait can never join a group made in it. */
	cq_press_reset();
	cq_lock_take();
	cq_switch_gate = on ? 1 : 0;
	cq_lock_give();
}

int cq_switch_gate_open(void) {
	int r;
	cq_lock_take();
	r = cq_switch_gate;
	cq_lock_give();
	return r;
}

/* 1 when a request is waiting AND the gate is open; the request is taken. */
int cq_cal_take_request(void) {
	int r = 0;
	cq_lock_take();
	if (cq_cal_gate && cq_cal_requested) {
		cq_cal_requested = 0;
		r = 1;
	}
	cq_lock_give();
	return r;
}

/* 1 when a request is waiting, regardless of the gate; the request is taken.
 * Used only inside the "calibration damaged" wait, which is itself a place
 * the user is asked to calibrate. */
int cq_cal_take_request_ungated(void) {
	int r;
	cq_lock_take();
	r = cq_cal_requested;
	cq_cal_requested = 0;
	cq_lock_give();
	return r;
}

void cq_cal_request_scope(int on) {
	cq_lock_take();
	cq_cal_in_request = on ? 1 : 0;
	cq_cal_cancel = 0;
	if (!on)
		cq_cal_requested = 0;   /* a second press during it is spent by it */
	cq_lock_give();
}

int cq_cal_take_cancel(void) {
	int r;
	cq_lock_take();
	r = cq_cal_cancel;
	cq_cal_cancel = 0;
	cq_lock_give();
	return r;
}

/* Non-blocking: the next waiting key, or CQ_KEY_NONE. A goto is dropped. */
int cq_poll_char(void) {
	int k = cq_cmd_take_key();
	return (k == CQ_KEY_GOTO || k == CQ_KEY_FILE_AS || k == CQ_KEY_RESUME
	        || k == CQ_KEY_HOLD)
	       ? CQ_KEY_NONE : k;
}

void cq_sleep_poll(void) {
	cq_sleep_ms(20);
}

/* ------------------------------------------------------------------ */
/* CHROMIQ_EXT: the pause between pages (jctay 149802, Basti 2026-10-23). */

void cq_hold_clear(void) {
	cq_lock_take();
	cq_hold_strip[0] = '\0';
	cq_lock_give();
}

/* 1 when the GUI asked to hold after *strip*; the request is spent. */
int cq_hold_matches(const char *strip) {
	int r = 0;
	cq_lock_take();
	if (strip != NULL && cq_hold_strip[0] != '\0'
	 && strcmp(cq_hold_strip, strip) == 0) {
		r = 1;
		cq_hold_strip[0] = '\0';
	}
	cq_lock_give();
	return r;
}

/* The hold itself. The resume and the four moves are taken here; anything
 * else that arrives (done, quit, file_as, ok, a calibration request) is LEFT
 * where it is, so the strip menu that follows acts on it exactly as it would
 * have without the hold. Nothing here ever triggers a reading. */
int cq_hold_wait(char *label, size_t labellen) {
	for (;;) {
		int k, r = CQ_KEY_NONE;
		cq_lock_take();
		k = cq_pending_key;
		if (k == CQ_KEY_HOLD) {
			/* Already holding: a second hold changes nothing. */
			cq_pending_key = CQ_KEY_NONE;
		} else if (k == CQ_KEY_RESUME || k == 'f' || k == 'b' || k == 'n') {
			cq_pending_key = CQ_KEY_NONE;
			r = k;
		} else if (k == CQ_KEY_GOTO) {
			cq_pending_key = CQ_KEY_NONE;
			if (label != NULL && labellen > 0) {
				strncpy(label, cq_goto_label, labellen - 1);
				label[labellen - 1] = '\0';
			}
			r = k;
		} else if (k != CQ_KEY_NONE || cq_cal_requested) {
			r = CQ_HOLD_OTHER;
		}
		cq_lock_give();
		if (r != CQ_KEY_NONE)
			return r;
		cq_press_group_poll("held");	/* inert unless gestures + gate */
		cq_sleep_ms(20);
	}
}

/* ------------------------------------------------------------------ */
/* CHROMIQ_EXT: groups of presses of the instrument's button (Basti,   */
/* 2026-10-25; jctay, forum 149841). See chromiq_ext.h. Everything     */
/* here is inert unless --gestures was given AND the strip or patch    */
/* loop found an instrument that reports presses (cq_gesture_activate) */

int cq_gesture_ms = 0;
int cq_gesture_counts = 0;
int cq_button_test = 0;
volatile int cq_stdin_eof = 0;

static volatile int cq_gest_on = 0;       /* activated for this session */
static volatile int cq_press_listening = 0;
#define CQ_PRESS_MAX 16
static double cq_press_t[CQ_PRESS_MAX];
static int    cq_press_n = 0;

/* A press group is never longer than this from its first press, however
 * fast someone keeps pressing: the reader must not wait for ever. */
#define CQ_GROUP_MAX_MS 6000.0

double cq_now_ms(void) {
#ifdef NT
	return (double)GetTickCount64();
#else
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1.0e6;
#endif
}

void cq_gesture_activate(int on) {
	cq_lock_take();
	cq_gest_on = (on && cq_gesture_ms > 0) ? 1 : 0;
	cq_press_n = 0;
	cq_press_listening = 0;
	cq_lock_give();
}

int cq_gesture_active(void) {
	return cq_gest_on;
}

void cq_press_reset(void) {
	cq_lock_take();
	cq_press_n = 0;
	cq_lock_give();
}

void cq_press_listen(int on) {
	cq_lock_take();
	cq_press_listening = on ? 1 : 0;
	if (!on)
		cq_press_n = 0;
	cq_lock_give();
}

/* The press that triggered a waiting strip or patch. The driver counts it as
 * the trigger and never reports it (hide_switch, munki_imp.c:2073,
 * i1pro_imp.c:2990), so its time is the moment the reader learns of it. */
void cq_press_note_trigger(void) {
	if (!cq_gest_on)
		return;
	cq_lock_take();
	cq_press_t[0] = cq_now_ms();
	cq_press_n = 1;
	cq_press_listening = 1;
	cq_lock_give();
}

int cq_press_from_driver(void) {
	int taken = 0;
	if (!cq_gest_on)
		return 0;
	cq_lock_take();
	if (cq_press_listening || cq_switch_gate) {
		if (cq_press_n < CQ_PRESS_MAX)
			cq_press_t[cq_press_n++] = cq_now_ms();
	}
	taken = 1;	/* with gestures on, the gate's own reporting is ours */
	cq_lock_give();
	return taken;
}

/* The chain that starts at the first press noted: its size, its gaps, and
 * whether it is complete (quiet for longer than the wait, or too long). */
static int cq_press_chain_locked(int *gaps_ms, int maxgaps, int *complete) {
	int k, i;
	double now = cq_now_ms();
	if (cq_press_n == 0) {
		*complete = 0;
		return 0;
	}
	for (k = 1; k < cq_press_n; k++) {
		double g = cq_press_t[k] - cq_press_t[k - 1];
		if (g > (double)cq_gesture_ms)
			break;
	}
	for (i = 1; i < k && i - 1 < maxgaps; i++)
		gaps_ms[i - 1] = (int)(cq_press_t[i] - cq_press_t[i - 1] + 0.5);
	*complete = (now - cq_press_t[k - 1] > (double)cq_gesture_ms)
	         || (now - cq_press_t[0] > CQ_GROUP_MAX_MS)
	         || (k >= CQ_PRESS_MAX);
	return k;
}

int cq_press_wait_group(int *gaps_ms, int maxgaps) {
	for (;;) {
		int k, done;
		cq_lock_take();
		k = cq_press_chain_locked(gaps_ms, maxgaps, &done);
		if (k == 0 || done) {
			cq_press_n = 0;
			cq_press_listening = 0;
			cq_lock_give();
			return k;
		}
		cq_lock_give();
		cq_sleep_ms(20);
	}
}

int cq_gesture_counts_for(int n) {
	return (n == 2 || n == 3) && (cq_gesture_counts & (1 << n)) != 0;
}

void cq_press_group_json(char *buf, size_t len, int n, const int *gaps_ms) {
	size_t o;
	int i;
	o = (size_t)snprintf(buf, len, ",\"presses\":%d,\"gaps_ms\":[", n);
	for (i = 0; i + 1 < n && o + 16 < len; i++)
		o += (size_t)snprintf(buf + o, len - o, "%s%d", i ? "," : "",
		                      gaps_ms[i]);
	if (o + 2 < len)
		snprintf(buf + o, len - o, "]");
}

void cq_press_group_poll(const char *where) {
	int gaps[CQ_PRESS_MAX], k = 0, done = 0;
	char js[160];
	if (!cq_gest_on)
		return;
	cq_lock_take();
	if (cq_switch_gate) {
		k = cq_press_chain_locked(gaps, CQ_PRESS_MAX, &done);
		if (k > 0 && done)
			cq_press_n = 0;
	}
	cq_lock_give();
	if (k == 0 || !done)
		return;
	if (cq_button_test) {
		/* Preferences' "Try it": every group, as it was recognised. */
		cq_press_group_json(js, sizeof(js), k, gaps);
		cq_emit_raw("{\"event\":\"press_group\"%s}", js);
	} else if (cq_gesture_counts_for(k)) {
		cq_press_group_json(js, sizeof(js), k, gaps);
		cq_emit_raw("{\"event\":\"gesture\"%s,\"where\":\"%s\"}", js, where);
	} else {
		/* One press, or a group with no action: what one press is today. */
		cq_emit_simple("switch");
	}
}

/* How long ago the trigger of the reading now being decided was noted, in
 * ms, or -1 when none was (a command, a key, or gestures off). */
double cq_press_trigger_age_ms(void) {
	double r = -1.0;
	if (!cq_gest_on)
		return -1.0;
	cq_lock_take();
	if (cq_press_listening && cq_press_n > 0)
		r = cq_now_ms() - cq_press_t[0];
	cq_lock_give();
	return r;
}
