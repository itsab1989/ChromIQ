/* JSON-mode calibration handler for chromiq-chartread.
 *
 * A faithful port of instappsup.c's inst_handle_calibrate() state machine
 * (Argyll 3.5.0, GPLv2+) with the two console touch points replaced:
 * prompts become cal_* JSON events, and "hit any key" waits consume the
 * command channel instead of stdin characters. The calibrate()/calt/calc
 * loop is IDENTICAL — only the user-interaction edge differs.
 *
 * AGPL-3.0 for the combination — see ../instlib/License.txt.
 * Part of ChromIQ issue #126. */

#ifdef SALONEINSTLIB
#include "sa_config.h"
#else
#include "aconfig.h"
#endif
#include <stdio.h>
#include <string.h>
#include "numsup.h"
#include "cgats.h"
#include "xspect.h"
#include "conv.h"
#include "insttypes.h"
#include "icoms.h"
#include "inst.h"

#include "chromiq_ext.h"

/* Short machine-readable name for each calibration condition, plus the
 * human sentence chartread would have printed. The GUI shows its own
 * translated text keyed on `cond`; `text` is a debugging aid. */
static const char *cq_calc_name(inst_cal_cond calc) {
	switch (calc & inst_calc_cond_mask) {
		case inst_calc_uop_ref_white:   return "uop_ref_white";
		case inst_calc_uop_trans_white: return "uop_trans_white";
		case inst_calc_uop_trans_dark:  return "uop_trans_dark";
		case inst_calc_man_ref_white:   return "man_ref_white";
		case inst_calc_man_ref_whitek:  return "man_ref_whitek";
		case inst_calc_man_ref_dark:    return "man_ref_dark";
		case inst_calc_man_dark_gloss:  return "man_dark_gloss";
		case inst_calc_man_em_dark:     return "man_em_dark";
		case inst_calc_man_am_dark:     return "man_am_dark";
		case inst_calc_man_cal_smode:   return "man_cal_smode";
		case inst_calc_man_trans_white: return "man_trans_white";
		case inst_calc_man_trans_dark:  return "man_trans_dark";
		case inst_calc_change_filter:   return "change_filter";
		case inst_calc_message:         return "message";
		case inst_calc_emis_white:      return "emis_white";
		case inst_calc_emis_80pc:       return "emis_80pc";
		case inst_calc_emis_grey:
		case inst_calc_emis_grey_darker:
		case inst_calc_emis_grey_ligher: return "emis_grey";
		default:                        return "unknown";
	}
}

inst_code cq_handle_calibrate(inst *p, inst_cal_type calt, inst_cal_cond calc,
	int doimmediately) {
	inst_code ev;
	int usermes = 0;
	inst_calc_id_type idtype = inst_calc_id_none;
	char id[200];
	int ch;

	a1logd(p->log, 1, "cq_handle_calibrate called\n");
	p->last_cal_ec = 0;
	id[0] = '\0';

	for (;;) {
		/* Cleared every round: a driver that sets no identifier must not leave
		 * the previous round's — or the stack's — contents behind. */
		idtype = inst_calc_id_none;
		id[0] = '\0';
		ev = p->calibrate(p, &calt, &calc, &idtype, id);

		if ((ev & inst_mask) == inst_ok) {
			if ((calc & inst_calc_cond_mask) == inst_calc_message) {
				char esc[256];
				cq_json_escape(esc, sizeof(esc), id);
				cq_emit_raw("{\"event\":\"cal_message\",\"text\":\"%s\"}", esc);
			}
			if (usermes)
				cq_emit_simple("cal_done");
			return ev;
		}

		if ((ev & inst_mask) == inst_user_abort)
			return ev;

		if ((ev & inst_mask) != inst_cal_setup) {
			if ((ev & inst_mask) == inst_unsupported)
				return inst_unsupported;

			cq_emit_error("cal_failed", p->inst_interp_error(p, ev));
			p->last_cal_ec = ev;

			if (doimmediately)
				return inst_user_abort;

			/* Wait for retry (any command) or quit */
			ch = cq_wait_char();
			if (ch == 0x1b || ch == 0x3 || ch == 'q' || ch == 'Q')
				return inst_user_abort;

		} else {
			char esc[256];
			/* The identifier buffer is only filled for conditions that carry
			 * one — idtype says which, and upstream prints it solely for
			 * inst_calc_message. Serialising it regardless handed the GUI
			 * whatever was on the stack: a real ColorMunki asking for its
			 * calibration position produced "4k2\x9f\x01". Emit it only when
			 * it means something. */
			esc[0] = '\0';
			if (idtype != inst_calc_id_none)
				cq_json_escape(esc, sizeof(esc), id);
			cq_emit_raw(
				"{\"event\":\"cal_required\",\"cond\":\"%s\",\"id\":\"%s\","
				"\"optional\":%s}",
				cq_calc_name(calc), esc,
				(calc & inst_calc_optional_flag) ? "true" : "false");
			usermes = 1;

			/* Identical wait rule to upstream: no wait when immediate, or
			 * when the condition is click-on-tile (whitek). */
			if (!doimmediately
			 && (calc & inst_calc_cond_mask) != inst_calc_man_ref_whitek) {
				ch = cq_wait_char();
				if ((calc & inst_calc_optional_flag) != 0 && (ch == 's' || ch == 'S')) {
					cq_emit_simple("cal_skipped");
					goto oloop;
				}
				if (ch == 0x1b || ch == 0x3 || ch == 'q' || ch == 'Q')
					return inst_user_abort;
			}
			calc &= inst_calc_cond_mask;
		}
 oloop:;
	}
}

/* CHROMIQ_EXT: a calibration the USER asked for, between strips or patches
 * (K, or the Calibrate button; Knut #182 5965478577, Basti 5965500670).
 *
 * The same calibrate()/calt/calc loop as above, with inst_calt_available,
 * and three differences that all follow from readings already existing:
 *
 *  * Cancel at a placement prompt is {"cmd":"cal_cancel"}, not Esc, and it
 *    returns CQ_CALREQ_CANCELLED. The session carries on. The driver asks for
 *    placement BEFORE it measures anything (i1pro_imp.c:2569-2572, calc
 *    none -> I1PRO_CAL_SETUP), so the old calibration still stands.
 *  * A hard failure is NOT retried here and NOT reported as cal_failed (that
 *    event ends the session and triggers the stock fallback). It returns
 *    CQ_CALREQ_FAILED, and the caller locks reading: an i1Pro measures its
 *    white straight into cal_factor[] and checks it afterwards, so after a
 *    failure the instrument would read on without complaint against a raw
 *    white reading (i1pro_imp.c:2230, 2429-2433; challenge 1c).
 *  * Nothing to calibrate is CQ_CALREQ_UNAVAILABLE rather than a silent
 *    inst_ok, so the GUI always hears one result.
 *
 * Keys waiting in the slot from before the prompt are dropped before it is
 * shown: a stale "any key" would otherwise start the measurement before the
 * instrument is on its tile. */
int cq_run_requested_calibration(inst *p, int *prompted, char *detail,
	size_t detail_len) {
	inst_code ev;
	inst_cal_type calt = inst_calt_available;
	inst_cal_cond calc = inst_calc_none;
	inst_cal_type needed = inst_calt_none, available = inst_calt_none;
	inst_calc_id_type idtype;
	char id[200];
	int ch;

	*prompted = 0;
	if (detail_len > 0)
		detail[0] = '\0';
	if (p == NULL)
		return CQ_CALREQ_UNAVAILABLE;

	a1logd(p->log, 1, "cq_run_requested_calibration called\n");
	if (p->get_n_a_cals == NULL
	 || p->get_n_a_cals(p, &needed, &available) != inst_ok
	 || (available & inst_calt_n_dfrble_mask) == 0)
		return CQ_CALREQ_UNAVAILABLE;

	p->last_cal_ec = 0;
	for (;;) {
		idtype = inst_calc_id_none;
		id[0] = '\0';
		ev = p->calibrate(p, &calt, &calc, &idtype, id);

		if ((ev & inst_mask) == inst_ok) {
			if ((calc & inst_calc_cond_mask) == inst_calc_message) {
				char esc[256];
				cq_json_escape(esc, sizeof(esc), id);
				cq_emit_raw("{\"event\":\"cal_message\",\"text\":\"%s\"}", esc);
			}
			return CQ_CALREQ_DONE;
		}
		if ((ev & inst_mask) == inst_unsupported)
			return CQ_CALREQ_UNAVAILABLE;
		if ((ev & inst_mask) == inst_user_abort)
			return CQ_CALREQ_CANCELLED;

		if ((ev & inst_mask) != inst_cal_setup) {
			p->last_cal_ec = ev;
			if (detail_len > 0) {
				const char *t = p->inst_interp_error(p, ev);
				strncpy(detail, t != NULL ? t : "", detail_len - 1);
				detail[detail_len - 1] = '\0';
			}
			return CQ_CALREQ_FAILED;
		}

		/* Placement prompt. */
		{
			char esc[256];
			esc[0] = '\0';
			if (idtype != inst_calc_id_none)
				cq_json_escape(esc, sizeof(esc), id);
			(void)cq_poll_char();          /* drop a stale key */
			(void)cq_cal_take_cancel();
			cq_emit_raw(
				"{\"event\":\"cal_required\",\"cond\":\"%s\",\"id\":\"%s\","
				"\"optional\":%s,\"requested\":true}",
				cq_calc_name(calc), esc,
				(calc & inst_calc_optional_flag) ? "true" : "false");
			*prompted = 1;
		}
		/* Same wait rule as upstream: no wait for click-on-tile (whitek). */
		if ((calc & inst_calc_cond_mask) != inst_calc_man_ref_whitek) {
			for (;;) {
				if (cq_cal_take_cancel())
					return CQ_CALREQ_CANCELLED;
				ch = cq_poll_char();
				if (ch == CQ_KEY_NONE) {
					cq_sleep_poll();
					continue;
				}
				/* Esc/q here is a cancel of THIS calibration, never a quit:
				 * the GUI never sends one, and if it ever did, keeping the
				 * session is the outcome that loses nothing. */
				if (ch == 0x1b || ch == 0x3 || ch == 'q' || ch == 'Q')
					return CQ_CALREQ_CANCELLED;
				if ((calc & inst_calc_optional_flag) != 0
				 && (ch == 's' || ch == 'S')) {
					/* As upstream: the flag stays on calc, which is how
					 * the driver learns the step was skipped. */
					cq_emit_simple("cal_skipped");
					goto rloop;
				}
				break;                      /* any other key: proceed */
			}
		}
		calc &= inst_calc_cond_mask;
 rloop:;
	}
}
