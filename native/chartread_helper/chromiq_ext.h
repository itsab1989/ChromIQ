/* ChromIQ extensions to chartread (issue #126).
 *
 * Everything ChromIQ adds on top of stock chartread lives behind this
 * header + chromiq_json.c / chromiq_replay.c. Without --json / --replay on
 * the command line the fork behaves exactly like upstream chartread.
 *
 * Licensed AGPL-3.0 like chartread.c itself (see ../instlib/License.txt).
 */
#ifndef CHROMIQ_EXT_H
#define CHROMIQ_EXT_H

#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- mode flags (set once during argument parsing) -------------------- */
extern int cq_json;      /* 1 = emit JSON events, accept JSON commands     */
extern int cq_autosave;  /* 1 = write .ti3 after every accepted strip      */
extern int cq_safenet;   /* 1 = misalignment safety net (opt-in, #50)      */
extern int cq_xychart;   /* 1 = engine handles XY/chart modes (else fall back) */

/* ---- JSON event emission (no-ops when cq_json == 0) ------------------- */
void cq_emit_raw(const char *fmt, ...);   /* fmt is a complete JSON object */

/* #202: ONE JSON LINE IS WRITTEN WHOLE, WHICHEVER THREAD WRITES IT.
 * The scan_ready event comes from the instrument driver's helper thread
 * (inst.c delayed_scan_ready) while the main thread may be in the middle of a
 * multi-call event such as strip_read. Every JSON writer holds stdout's own
 * stdio lock for the whole line: it is recursive, and it is the very lock each
 * printf takes, so nothing can land inside a line. */
#ifdef NT
# define cq_out_lock()   _lock_file(stdout)
# define cq_out_unlock() _unlock_file(stdout)
#else
# define cq_out_lock()   flockfile(stdout)
# define cq_out_unlock() funlockfile(stdout)
#endif
void cq_emit_simple(const char *event);   /* {"event":"..."} */
void cq_emit_error(const char *kind, const char *detail);
void cq_json_escape(char *dst, size_t dstlen, const char *src);
/* A STALENESS MARKER FOR THE COMMITTED BINARY.
 *
 * ChromIQ.spec bundles native/chromiq-chartread — a build product committed to
 * the repository — while the engine prefers the CMake build tree. So a stale
 * bundled copy is invisible in a checkout: everything a developer runs uses the
 * fresh binary, and only the packaged app gets the old one.
 *
 * tests/test_cr30_packaging.py greps the committed binary for this string.
 * It used to grep for "CR30", which every build since the branch started
 * contains — so it stayed green over a binary that was months out of date.
 *
 * ⚠ BUMP THIS IN THE SAME COMMIT AS ANY CHANGE TO THE HELPER, and rebuild and
 * commit native/chromiq-chartread. The test tells you the expected value. */
#define CQ_HELPER_BUILD "chromiq-chartread 2026-10-03 calibrate-on-request"
const char *cq_helper_build_string(void);


/* ---- command channel ---------------------------------------------------
 * A background thread reads stdin lines; commands are mapped to the same
 * key codes chartread's console path uses, and handed to the instrument
 * ui-callback poll exactly where console keys are handed over today.
 * cq_take_goto() additionally reports a pending goto target (strip label),
 * valid when the last taken key was CQ_KEY_GOTO. */
#define CQ_KEY_NONE  0
#define CQ_KEY_GOTO  1000  /* internal pseudo-key for {"cmd":"goto"} */
void  cq_cmd_start(void);          /* start the stdin command thread */
int   cq_cmd_take_key(void);       /* CQ_KEY_NONE if no command pending */
const char *cq_take_goto(void);    /* target strip label for CQ_KEY_GOTO */

/* Blocking prompt read: in JSON mode polls the command queue (console is
 * never touched — stdin belongs to the command channel); otherwise falls
 * back to the console like stock chartread. */
int cq_wait_char(void);

/* #159: block for one line on the external-values (-x) channel. Fed by
 * {"cmd":"value","xyz":"X Y Z"} and by every key command, mirrored as a
 * one-character line. Needed because in JSON mode stdin belongs to the command
 * reader, so -x's own con_fgets can never succeed. */
int cq_wait_line(char *buf, int size);
int cq_line_overflow_count(void);  /* lines refused: queue full (protocol abuse) */

/* ---- a calibration the user asks for during a measurement -------------
 * {"cmd":"calibrate"} raises a flag of its own (never the key slot, never
 * the -x line queue). cq_uicallback turns it into a 'k' command only at
 * inst_armed and only while the strip or patch loop holds the gate open, so
 * it is acted on while the reader waits for the next strip or patch and
 * nowhere else -- not in a prompt, not in the whole-sheet (XY) loop.
 * {"cmd":"cal_cancel"} is honoured only inside that calibration. */
void cq_cal_gate_set(int on);
int  cq_cal_take_request(void);          /* gated */
int  cq_cal_take_request_ungated(void);  /* the "calibration damaged" wait */
void cq_cal_request_scope(int on);
int  cq_cal_take_cancel(void);
int  cq_poll_char(void);                 /* non-blocking key, or CQ_KEY_NONE */
void cq_sleep_poll(void);                /* the 20 ms poll interval */

/* Outcome of one requested calibration (cq_run_requested_calibration). */
#define CQ_CALREQ_DONE        0
#define CQ_CALREQ_CANCELLED   1
#define CQ_CALREQ_FAILED      2
#define CQ_CALREQ_UNAVAILABLE 3

/* ---- replay instrument -------------------------------------------------
 * cq_replay_path != NULL enables replay mode: no USB, readings come from a
 * replay script (see chromiq_replay.c header comment for the format). */
extern const char *cq_replay_path;
int  cq_replay_active(void);
int  cq_replay_load(const char *path);
/* Arm the replay's spot instrument with the current patch's expected XYZ,
 * so a headless patch-by-patch read echoes it back (measured == expected).
 * No-op unless replay mode is active. */
void cq_replay_arm_spot(const double xyz[3]);

/* Pending swipe injected by the command channel ({"cmd":"swipe", ...}) */
extern volatile int cq_swipe_pending;
extern char cq_swipe_as[8];
extern int  cq_swipe_reversed;
extern char cq_swipe_fault[16];

/* #202: a pending instrument trigger injected by {"cmd":"trigger"} (replay
 * only). The replay instrument then does what the i1Pro driver does when its
 * button is pressed: reports inst_triggered (scan_started), and raises the
 * ready-to-scan moment after `cq_trigger_ready_ms` through Argyll's own
 * issue_scan_ready(). Default 700 ms = the i1Pro's 200 ms + 0.5 s lamp time
 * (i1pro_imp.c:3197). */
extern volatile int cq_trigger_pending;
extern int cq_trigger_ready_ms;

/* Declarations that need Argyll's inst types — visible only to translation
 * units that include inst.h first. */
#ifdef INST_H
inst *cq_new_replay_inst(a1log *log,
	inst_code (*uicallback)(void *cntx, inst_ui_purp purp), void *cntx);
/* JSON-mode replacement for instappsup's inst_handle_calibrate(): same
 * state machine, but prompts become cal_* events and answers arrive as
 * commands. Never reads the console. */
inst_code cq_handle_calibrate(inst *p, inst_cal_type calt, inst_cal_cond calc,
	int doimmediately);
/* A calibration the user asked for: inst_calt_available, with prompts that
 * carry "requested":true and a Cancel (cal_cancel) that keeps the session.
 * Emits no terminal event itself -- the caller emits one cal_result. Fills
 * *prompted (a placement prompt was shown) and detail (the failure). */
int cq_run_requested_calibration(inst *p, int *prompted, char *detail,
	size_t detail_len);
/* The JSON-mode uicallback: identical classification to instappsup's
 * def_uicallback, with the command queue as the key source. */
inst_code cq_uicallback(void *cntx, inst_ui_purp purp);
/* #202: JSON-mode instrument event callback. On inst_event_scan_ready it plays
 * the beep the driver plays when no callback is registered, then emits
 * {"event":"scan_ready"}. Runs on Argyll's helper thread. */
void cq_event_callback(void *cntx, inst_event_type event);
#endif /* INST_H */

#ifdef __cplusplus
}
#endif
#endif /* CHROMIQ_EXT_H */
