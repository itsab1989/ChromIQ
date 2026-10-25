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
#define CQ_HELPER_BUILD "chromiq-chartread 2026-10-25 legacy-labels+calibrate-on-request+file-as+atomic-autosave+button-retry+file-as-keeps-earlier+hold-after+hold-here+hold-here-patch+button-gestures+exit-guard+save-after-close"
const char *cq_helper_build_string(void);


/* ---- command channel ---------------------------------------------------
 * A background thread reads stdin lines; commands are mapped to the same
 * key codes chartread's console path uses, and handed to the instrument
 * ui-callback poll exactly where console keys are handed over today.
 * cq_take_goto() additionally reports a pending goto target (strip label),
 * valid when the last taken key was CQ_KEY_GOTO. */
#define CQ_KEY_NONE  0
#define CQ_KEY_GOTO  1000  /* internal pseudo-key for {"cmd":"goto"} */
/* {"cmd":"file_as","strip":"C","as":"B"} (strip mode, Knut #182 6102031563):
 * the reading the engine filed under strip C was strip B. The strip loop
 * moves C's values to B, leaves C unread and puts the reader on C. */
#define CQ_KEY_FILE_AS 1001
const char *cq_take_file_as(void); /* "as" label for CQ_KEY_FILE_AS; the
                                      "strip" label is cq_take_goto()'s */
int cq_take_file_as_keep(void);    /* nz: "earlier":"keep" -- the strip the
                                      reading came off gets back the reading
                                      it had before that swipe (2026-10-21) */
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

/* ---- the instrument's button as Retry (B1, Basti 2026-10-21) ----------
 * The strip loop opens this gate only around its wait at the misread
 * prompt. cq_event_callback turns an inst_event_switch into
 * {"event":"switch"} only while it is open; every other prompt (Wrong Strip,
 * calibration, the menu) never sees a press reported. The misread error
 * event carries "button_retry":true when the connected instrument's driver
 * reports presses outside a scan (i1Pro, i1Pro 2, i1Pro 3, ColorMunki). */
void cq_switch_gate_set(int on);
int  cq_switch_gate_open(void);
/* Replay only: {"cmd":"switch"} -- a press of the fake instrument's button. */
void cq_replay_switch_press(void);

/* ---- groups of presses of the instrument's button ----------------------
 * (Basti 2026-10-25, after jctay's forum post 149841.) OFF unless the GUI
 * starts the engine with --gestures <ms>:<counts>; without it every line in
 * this block is inert and the engine behaves byte for byte as before.
 *
 * With it, and only for an instrument whose driver reports presses outside a
 * scan (cq_button_retry_ok: the i1Pro line and the ColorMunki), every press
 * the driver reports while the engine LISTENS is timed: from the moment a
 * waiting strip or patch is triggered until its reading is decided, and while
 * the switch gate is open (the misread prompt and the holds). Presses whose
 * gaps are each at most <ms> form one group. A group of 2 or 3 presses whose
 * count is in <counts> ("23" = both) is a gesture; anything else counts as a
 * single press, i.e. exactly what one press does today, only after <ms> of
 * quiet. See the strip and patch loops for where a gesture can be made and
 * why a reading can never become one. */
extern int cq_gesture_ms;       /* 0 = off: the wait for a further press */
extern int cq_gesture_counts;   /* bit n set: an n-press group has an action */
extern int cq_button_test;      /* --button-test: Preferences' "Try it" */
void   cq_gesture_activate(int on);  /* this session's instrument can do it */
int    cq_gesture_active(void);
double cq_now_ms(void);              /* a monotonic clock, in ms */
void   cq_press_reset(void);         /* forget every press noted so far */
void   cq_press_listen(int on);      /* note presses outside the gate too */
void   cq_press_note_trigger(void);  /* a waiting strip or patch was triggered */
double cq_press_trigger_age_ms(void); /* ms since that trigger, -1 if none */
/* From the event callback: 1 when the press was taken here (gestures on). */
int    cq_press_from_driver(void);
/* Block until the group that began with the trigger is complete; returns its
 * size (0: no trigger was noted) and fills gaps_ms[0..size-2]. Presses after
 * a gap longer than the wait belong to no group and are dropped. */
int    cq_press_wait_group(int *gaps_ms, int maxgaps);
/* 1 when a group of *n* presses is a gesture (2 or 3, and in --gestures). */
int    cq_gesture_counts_for(int n);
/* Format ,"presses":n,"gaps_ms":[..] into buf (for the events). */
void   cq_press_group_json(char *buf, size_t len, int n, const int *gaps_ms);
/* The gate's own grouping, called from every wait that has the gate open: a
 * complete group is reported as {"event":"switch"} (a single press, as
 * today) or {"event":"gesture",...,"where":"<where>"}. */
void   cq_press_group_poll(const char *where);
/* Replay only: {"cmd":"presses","at_ms":"0,300,650"}, a person pressing the
 * button at those times: a press at a waiting strip starts a scan that ends
 * "Reading is too short" 220 ms later, as a quick tap does on a ColorMunki. */
void   cq_replay_presses(const char *at_ms);
/* stdin has closed: nothing more will ever be asked (--button-test). */
extern volatile int cq_stdin_eof;

/* ---- the instrument is always let go (hand test, 2026-10-25) ------------
 * Basti's ColorMunki: after quit, Ctrl+C or its stdin closing, the engine
 * stayed alive and kept the instrument ("Device being used?") until SIGTERM.
 * Closing an instrument can block for ever in the driver (a switch thread
 * that never ends, a USB close inside the signal handler), and the ONLY
 * thing that frees a USB device for certain is the process ending. So, in
 * JSON mode, a watchdog thread ends the process with _exit() once a deadline
 * has passed: armed when stdin closes (nobody can ever ask again), when the
 * instrument is being closed (it->del, whatever path the engine ends by),
 * and on SIGINT / SIGTERM / SIGHUP. A clean ending is always quicker than
 * the deadline, so it changes nothing there. */
#define CQ_EXIT_GRACE_MS 1500
/* Once the instrument's close has RETURNED, the process has this long to
 * finish (the final .ti3 is written after the close): the close's own 1.5 s
 * must never cut that write short. */
#define CQ_EXIT_AFTER_CLOSE_MS 30000
void cq_exit_close_begin(void);           /* it->del starts: 1.5 s */
void cq_exit_close_end(void);             /* it->del returned: 30 s */
void cq_exit_deadline_arm(int ms);        /* never moves an earlier deadline */
void cq_exit_guard_start(void);           /* the watchdog thread */
void cq_exit_guard_signals(void);         /* our handlers, chained to the old */

/* ---- the pause between pages (jctay 149802, Basti 2026-10-23) ----------
 * {"cmd":"hold_after","strip":"F"}: once strip F has been read and accepted
 * (every question the engine asks about it answered), the strip loop does not
 * arm the next strip. It reports {"event":"held","strip":"F","button":b} and
 * waits, with the switch gate open, so a press of the instrument's button is
 * reported as {"event":"switch"} and can never start a scan. The GUI decides
 * which strips to hold after; every strip_ready forgets the request, so it
 * applies only to the strip it was sent for.
 *
 * In the hold: {"cmd":"resume"} goes on as the engine would have (next
 * unread); forward, back, next_unread and goto move from the strip just
 * read; any other command (done, quit, file_as, a calibration request) ends
 * the hold and is left waiting for the strip menu, which acts on it as
 * always. */
#define CQ_KEY_RESUME 1002   /* {"cmd":"resume"}: meaningful only in the hold */
#define CQ_HOLD_OTHER 1003   /* cq_hold_wait: a command is left for the menu */
/* {"cmd":"hold"} (agent 30, 2026-10-23): hold HERE, at the strip menu the
 * engine is waiting at, without reading anything. Sent by the GUI while a
 * window that finishes the measurement ("All Strips Read") is open, so a
 * press of the instrument's button cannot start a reading that would replace
 * a good strip behind that window. The hold is the one above (the switch gate
 * open, a press only reported); resume offers the SAME strip again, the moves
 * move from it, anything else is left for the menu. Taken only while a strip
 * is armed (inst_armed); anywhere else it is dropped, never a trigger.
 * Patch by patch the same, at the patch menu (agent 33, 2026-10-23). */
#define CQ_KEY_HOLD   1004
void cq_hold_clear(void);
int  cq_hold_matches(const char *strip);
/* Block in the hold. Returns CQ_KEY_RESUME, 'f', 'b', 'n', CQ_KEY_GOTO (its
 * label copied into *label*) or CQ_HOLD_OTHER. */
int  cq_hold_wait(char *label, size_t labellen);

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
extern char cq_swipe_reason[96];   /* B1: a misread's driver sentence */

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
