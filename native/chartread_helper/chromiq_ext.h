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
void cq_emit_simple(const char *event);   /* {"event":"..."} */
void cq_emit_error(const char *kind, const char *detail);
void cq_json_escape(char *dst, size_t dstlen, const char *src);

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
/* The JSON-mode uicallback: identical classification to instappsup's
 * def_uicallback, with the command queue as the key source. */
inst_code cq_uicallback(void *cntx, inst_ui_purp purp);
#endif /* INST_H */

#ifdef __cplusplus
}
#endif
#endif /* CHROMIQ_EXT_H */
