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
	 * object at column 0 so the GUI's line decoder always sees it clean. */
	fputc('\n', stdout);
	va_start(args, fmt);
	vfprintf(stdout, fmt, args);
	va_end(args);
	fputc('\n', stdout);
	fflush(stdout);
}

void cq_emit_simple(const char *event) {
	cq_emit_raw("{\"event\":\"%s\"}", event);
}

void cq_emit_error(const char *kind, const char *detail) {
	char esc[512];
	cq_json_escape(esc, sizeof(esc), detail != NULL ? detail : "");
	cq_emit_raw("{\"event\":\"error\",\"kind\":\"%s\",\"detail\":\"%s\"}", kind, esc);
}

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

	if (strcmp(cmd, "goto") == 0
	 && (cq_json_get(line, "strip", gl, sizeof(gl))
	  || cq_json_get(line, "patch", gl, sizeof(gl))))
		key = CQ_KEY_GOTO;
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
	if (key == CQ_KEY_GOTO) {
		strncpy(cq_goto_label, gl, sizeof(cq_goto_label) - 1);
		cq_goto_label[sizeof(cq_goto_label) - 1] = '\0';
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

#ifdef NT
static unsigned __stdcall cq_reader(void *arg) {
#else
static void *cq_reader(void *arg) {
#endif
	char line[256];
	(void)arg;
	while (fgets(line, sizeof(line), stdin) != NULL)
		cq_handle_line(line);
#ifdef NT
	return 0;
#else
	return NULL;
#endif
}

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
volatile int cq_swipe_pending = 0;
char cq_swipe_as[8]      = "";
int  cq_swipe_reversed   = 0;
char cq_swipe_fault[16]  = "";

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
		if (k != CQ_KEY_NONE && k != CQ_KEY_GOTO)
			return k;
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
