/* Replay instrument for chromiq-chartread — a fake `inst` object that
 * feeds scripted readings through the REAL read_strips code path, so the
 * whole decision logic (recognition, warnings, autosave, F7-R) is
 * exercised without hardware.
 *
 * Replay script format (one directive per line, '#' comments):
 *   PATCHES <steps-per-pass>
 *   STRIP <pass-label>            begins a strip block
 *   <X> <Y> <Z>                   one patch reading (D50 XYZ, 0..100)
 *
 * All *faults* and *wrong swipes* are injected live via the JSON command
 * channel (see chromiq_json.c): {"cmd":"swipe"} triggers reading the armed
 * strip; optional fields "as":"<label>" (values of another strip),
 * "reversed":true, "fault":"misread|coms|needs_cal|wrong_config".
 *
 * AGPL-3.0 — see ../instlib/License.txt. Part of ChromIQ issue #126. */

#ifdef SALONEINSTLIB
#include "sa_config.h"
#else
#include "aconfig.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "numsup.h"
#include "cgats.h"
#include "xspect.h"
#include "conv.h"
#include "insttypes.h"
#include "icoms.h"
#include "inst.h"

#include "chromiq_ext.h"

const char *cq_replay_path = NULL;

int cq_replay_active(void) {
	return cq_replay_path != NULL;
}

/* ---------------- script storage ---------------- */

#define CQ_MAX_STRIPS 512
#define CQ_MAX_STEPS  64

typedef struct {
	char   label[8];
	int    n;
	double xyz[CQ_MAX_STEPS][3];
} cq_strip;

static cq_strip cq_strips[CQ_MAX_STRIPS];
static int      cq_nstrips = 0;
static int      cq_stipa = 0;

int cq_replay_load(const char *path) {
	FILE *fp;
	char line[256];
	cq_strip *cur = NULL;

	if ((fp = fopen(path, "r")) == NULL) {
		a1logw(g_log, "chromiq replay: can't open '%s'\n", path);
		return 1;
	}
	while (fgets(line, sizeof(line), fp) != NULL) {
		char lab[8];
		double x, y, z;
		if (line[0] == '#' || line[0] == '\n' || line[0] == '\r')
			continue;
		if (sscanf(line, "PATCHES %d", &cq_stipa) == 1)
			continue;
		if (sscanf(line, "STRIP %7s", lab) == 1) {
			if (cq_nstrips >= CQ_MAX_STRIPS) {
				fclose(fp);
				return 1;
			}
			cur = &cq_strips[cq_nstrips++];
			memset(cur, 0, sizeof(*cur));
			strncpy(cur->label, lab, sizeof(cur->label) - 1);
			continue;
		}
		if (cur != NULL && sscanf(line, "%lf %lf %lf", &x, &y, &z) == 3
		 && cur->n < CQ_MAX_STEPS) {
			cur->xyz[cur->n][0] = x;
			cur->xyz[cur->n][1] = y;
			cur->xyz[cur->n][2] = z;
			cur->n++;
		}
	}
	fclose(fp);
	a1logd(g_log, 1, "chromiq replay: %d strips of %d patches from '%s'\n",
	       cq_nstrips, cq_stipa, path);
	return cq_nstrips == 0;
}

static cq_strip *cq_find(const char *label) {
	int i;
	for (i = 0; i < cq_nstrips; i++)
		if (strcmp(cq_strips[i].label, label) == 0)
			return &cq_strips[i];
	return NULL;
}

/* ---------------- fake inst object ---------------- */

typedef struct _cq_inst {
	INST_OBJ_BASE
} cq_inst;

/* Minimal icoms stand-in: read_strips touches it->icom only for
 * port_type()/port_attr() guards (serial baud fallback, fast-serial
 * checks) — report a plain USB port so those branches stay inert. */
static icom_type cq_icom_port_type(struct _icoms *p) {
	(void)p;
	return icomt_usb;
}

static icom_type cq_icom_port_attr(struct _icoms *p) {
	(void)p;
	return icomt_usb;
}

static icoms cq_fake_icom;	/* zero-init; only the two members below are set */

static inst_code cq_init_coms(inst *p, baud_rate br, flow_control fc, double tout) {
	(void)br; (void)fc; (void)tout;
	p->gotcoms = 1;
	return inst_ok;
}

static inst_code cq_init_inst(inst *p) {
	p->inited = 1;
	return inst_ok;
}

static instType cq_get_itype(inst *p) {
	(void)p;
	return instI1Pro;		/* reads like an i1Pro strip reader */
}

static char *cq_get_serial_no(inst *p) {
	(void)p;
	return "";
}

static inst_code cq_get_set_opt(inst *p, inst_opt_type m, ...) {
	(void)p; (void)m;
	return inst_ok;
}

/* Which read mode the fake instrument advertises (CHROMIQ_REPLAY_MODE):
 * 0 = strip+spot (default), 2 = xy (SpectroScan), 3 = chart (i1iSis). Lets
 * tests drive the fork into rmode 2/3 to exercise the XY/chart engine paths
 * and the mode-fallback gate. */
static int cq_replay_mode = 0;

static void cq_capabilities(inst *p, inst_mode *cap1,
	inst2_capability *cap2, inst3_capability *cap3) {
	(void)p;
	if (cap1 != NULL) {
		if (cq_replay_mode == 3)
			*cap1 = inst_mode_ref_chart | inst_mode_reflection | inst_mode_colorimeter;
		else if (cq_replay_mode == 2)
			*cap1 = inst_mode_ref_xy | inst_mode_reflection | inst_mode_colorimeter;
		else
			*cap1 = inst_mode_ref_strip | inst_mode_ref_spot | inst_mode_reflection
			      | inst_mode_colorimeter;
	}
	/* No xy_holdrel / xy_locate: the fake table needs no hold/clear/sight
	 * steps, so the XY loop skips straight to read_xy. */
	if (cap2 != NULL)
		*cap2 = inst2_user_trig | inst2_user_switch_trig | inst2_bidi_scan;
	if (cap3 != NULL)
		*cap3 = inst3_none;
}

static inst_code cq_meas_config(inst *p, inst_mode *mmodes,
	inst_cal_cond *cconds, int *conf_ix) {
	(void)p; (void)mmodes; (void)cconds; (void)conf_ix;
	return inst_unsupported;
}

static inst_code cq_check_mode(inst *p, inst_mode m) {
	(void)p;
	if (cq_replay_mode == 3)
		return IMODETST(m, inst_mode_ref_chart) ? inst_ok : inst_unsupported;
	if (cq_replay_mode == 2)
		return IMODETST(m, inst_mode_ref_xy) ? inst_ok : inst_unsupported;
	if (IMODETST(m, inst_mode_ref_strip) || IMODETST(m, inst_mode_ref_spot))
		return inst_ok;
	return inst_unsupported;
}

/* Fill a value array with a synthetic neutral reading — enough to exercise the
 * whole-chart / whole-sheet transfer + JSON events + autosave without hardware.
 * (Faithful colours would need the real motorized table; the protocol is what
 * these paths are tested for.) */
static void cq_fill_synthetic(ipatch *vals, int n) {
	int i;
	for (i = 0; i < n; i++) {
		memset(&vals[i], 0, sizeof(ipatch));
		vals[i].XYZ[0] = 50.0;
		vals[i].XYZ[1] = 50.0;
		vals[i].XYZ[2] = 50.0;
		vals[i].XYZ_v = 1;
		vals[i].mtype = inst_mrt_reflective;
		vals[i].sp.spec_n = 0;
	}
}

static inst_code cq_read_chart(inst *p, int npatch, int pich, int sip,
	int *pis, int chid, ipatch *vals) {
	(void)p; (void)pich; (void)sip; (void)pis; (void)chid;
	cq_fill_synthetic(vals, npatch);
	return inst_ok;
}

static inst_code cq_read_xy(inst *p, int pis, int sip, int npatch,
	char *pname, char *sname, double ox, double oy, double ax, double ay,
	double aax, double aay, double px, double py, ipatch *vals) {
	(void)p; (void)pis; (void)sip; (void)pname; (void)sname;
	(void)ox; (void)oy; (void)ax; (void)ay; (void)aax; (void)aay; (void)px; (void)py;
	cq_fill_synthetic(vals, npatch);
	return inst_ok;
}

static inst_code cq_set_mode(inst *p, inst_mode m) {
	(void)p; (void)m;
	return inst_ok;
}

/* Optional calibration simulation (CHROMIQ_REPLAY_NEEDCAL): lets tests
 * exercise the JSON calibration handshake the real ColorMunki triggers —
 * one inst_cal_setup round (user positions the sensor), then inst_ok. */
static int cq_needcal_armed = 0;
static int cq_cal_step = 0;

static inst_cal_type cq_needs_calibration(inst *p) {
	(void)p;
	return cq_needcal_armed ? inst_calt_ref_white : inst_calt_none;
}

static inst_code cq_get_n_a_cals(inst *p, inst_cal_type *needed,
	inst_cal_type *available) {
	(void)p;
	if (needed != NULL)
		*needed = inst_calt_none;
	if (available != NULL)
		*available = inst_calt_none;
	return inst_ok;
}

static inst_code cq_calibrate(inst *p, inst_cal_type *calt, inst_cal_cond *calc,
	inst_calc_id_type *idtype, char id[CALIDLEN]) {
	(void)p; (void)idtype; (void)id;
	if (cq_needcal_armed && cq_cal_step == 0) {
		/* First round: ask the user to set the sensor to the white tile. */
		cq_cal_step = 1;
		if (calc != NULL)
			*calc = inst_calc_man_ref_white;
		return inst_cal_setup;
	}
	/* Done — clear the armed flag so the read loop proceeds. */
	cq_needcal_armed = 0;
	cq_cal_step = 0;
	if (calt != NULL)
		*calt = inst_calt_none;
	return inst_ok;
}

static void cq_set_uicallback(inst *p,
	inst_code (*uicallback)(void *cntx, inst_ui_purp purp), void *cntx) {
	p->uicallback = uicallback;
	p->uic_cntx = cntx;
}

static void cq_set_event_callback(inst *p,
	void (*eventcallback)(void *cntx, inst_event_type event), void *cntx) {
	p->eventcallback = eventcallback;
	p->event_cntx = cntx;
}

static char *cq_inst_interp_error(inst *p, inst_code ec) {
	(void)p;
	switch (ec & inst_mask) {
		case inst_misread:      return "Measurement misread (replay)";
		case inst_coms_fail:    return "Communications failure (replay)";
		case inst_needs_cal:    return "Instrument needs calibration (replay)";
		case inst_wrong_config: return "Sensor in wrong position (replay)";
		default:                return "Replay instrument error";
	}
}

static char *cq_interp_error(inst *p, int ec) {
	(void)p; (void)ec;
	return "replay";
}

static int cq_last_scomerr(inst *p) {
	(void)p;
	return 0;
}

static void cq_del(inst *p) {
	if (p != NULL) {
		if (p->log != NULL)
			del_a1log(p->log);
		free(p);
	}
}

/* The heart: block until the ui-callback reports a key/trigger, or the
 * command thread posts a swipe; then either return the user event exactly
 * like a real driver, or fill vals[] from the replay script. */
static inst_code cq_read_strip(inst *p, char *name, int npatch, char *pname,
	int sguide, double pwid, double gwid, double twid, ipatch *vals) {
	cq_inst *cq = (cq_inst *)p;
	cq_strip *st;
	int i;

	(void)name; (void)sguide; (void)pwid; (void)gwid; (void)twid;

	for (;;) {
		/* Give the registered uicallback a chance — console keys and JSON
		 * nav commands surface here as inst_user_abort/inst_user_trig,
		 * exactly like a real driver polling during its wait. */
		if (cq->uicallback != NULL) {
			inst_code uev = cq->uicallback(cq->uic_cntx, inst_armed);
			if (uev == inst_user_abort)
				return inst_user_abort;
			/* inst_user_trig means "read now": treat as swipe of the
			 * armed strip with no overrides. */
			if (uev == inst_user_trig) {
				cq_swipe_as[0] = '\0';
				cq_swipe_reversed = 0;
				cq_swipe_fault[0] = '\0';
				cq_swipe_pending = 1;
			}
		}

		if (cq_swipe_pending) {
			char fault[16];
			cq_swipe_pending = 0;
			strncpy(fault, cq_swipe_fault, sizeof(fault) - 1);
			fault[sizeof(fault) - 1] = '\0';

			if (fault[0] != '\0') {
				if (strcmp(fault, "misread") == 0)
					return inst_misread;
				if (strcmp(fault, "coms") == 0)
					return inst_coms_fail;
				if (strcmp(fault, "needs_cal") == 0)
					return inst_needs_cal;
				if (strcmp(fault, "wrong_config") == 0)
					return inst_wrong_config;
				return inst_misread;
			}

			st = cq_find(cq_swipe_as[0] != '\0' ? cq_swipe_as : pname);
			if (st == NULL || st->n < npatch)
				return inst_misread;	/* script gap reads as misread */

			for (i = 0; i < npatch; i++) {
				int six = cq_swipe_reversed ? npatch - 1 - i : i;
				memset(&vals[i], 0, sizeof(ipatch));
				vals[i].XYZ[0] = st->xyz[six][0];
				vals[i].XYZ[1] = st->xyz[six][1];
				vals[i].XYZ[2] = st->xyz[six][2];
				vals[i].XYZ_v = 1;
				vals[i].mtype = inst_mrt_reflective;
				vals[i].sp.spec_n = 0;
			}
			return inst_ok;
		}

		msec_sleep(20);
	}
}

/* ---------------- spot (patch-by-patch) reading ----------------
 * The spot loop arms the current patch's expected XYZ before each read
 * (cq_replay_arm_spot); the fake instrument echoes it back, so the whole
 * patch-by-patch path runs headless with measured == expected. A pending
 * fault (set via {"cmd":"swipe","fault":"…"}) is honoured once, exactly
 * like the strip path, so misread/coms/needs-cal recovery is testable. */
static double cq_spot_armed[3] = {0.0, 0.0, 0.0};

void cq_replay_arm_spot(const double xyz[3]) {
	cq_spot_armed[0] = xyz[0];
	cq_spot_armed[1] = xyz[1];
	cq_spot_armed[2] = xyz[2];
}

static inst_code cq_read_sample(inst *p, char *name, ipatch *val,
	instClamping clamp) {
	cq_inst *cq = (cq_inst *)p;
	(void)name; (void)clamp;

	for (;;) {
		/* Same poll as cq_read_strip: nav/goto commands surface as
		 * inst_user_abort, the read trigger as inst_user_trig. */
		if (cq->uicallback != NULL) {
			inst_code uev = cq->uicallback(cq->uic_cntx, inst_armed);
			if (uev == inst_user_abort)
				return inst_user_abort;
			if (uev == inst_user_trig) {
				char fault[16];
				strncpy(fault, cq_swipe_fault, sizeof(fault) - 1);
				fault[sizeof(fault) - 1] = '\0';
				cq_swipe_fault[0] = '\0';
				cq_swipe_pending = 0;
				if (fault[0] != '\0') {
					if (strcmp(fault, "misread") == 0)
						return inst_misread;
					if (strcmp(fault, "coms") == 0)
						return inst_coms_fail;
					if (strcmp(fault, "needs_cal") == 0)
						return inst_needs_cal;
					return inst_misread;
				}
				memset(val, 0, sizeof(ipatch));
				val->XYZ[0] = cq_spot_armed[0];
				val->XYZ[1] = cq_spot_armed[1];
				val->XYZ[2] = cq_spot_armed[2];
				val->XYZ_v = 1;
				val->mtype = inst_mrt_reflective;
				val->sp.spec_n = 0;
				return inst_ok;
			}
		}
		msec_sleep(20);
	}
}

/* Members read_strips touches but never exercises on the strip path. */
static inst_code cq_unsupported(void) {
	return inst_unsupported;
}

inst *cq_new_replay_inst(a1log *log,
	inst_code (*uicallback)(void *cntx, inst_ui_purp purp), void *cntx) {
	cq_inst *p;

	if ((p = (cq_inst *)calloc(1, sizeof(cq_inst))) == NULL)
		return NULL;

	/* Arm the calibration simulation from the environment (tests only). */
	cq_needcal_armed = (getenv("CHROMIQ_REPLAY_NEEDCAL") != NULL);
	cq_cal_step = 0;

	/* Which read mode to advertise (tests only): xy / chart / default. */
	{
		const char *rm = getenv("CHROMIQ_REPLAY_MODE");
		cq_replay_mode = 0;
		if (rm != NULL) {
			if (strcmp(rm, "chart") == 0)
				cq_replay_mode = 3;
			else if (strcmp(rm, "xy") == 0)
				cq_replay_mode = 2;
		}
	}

	p->log = new_a1log_d(log);
	p->init_coms          = cq_init_coms;
	p->init_inst          = cq_init_inst;
	p->get_itype          = cq_get_itype;
	p->get_serial_no      = cq_get_serial_no;
	p->get_set_opt        = cq_get_set_opt;
	p->capabilities       = cq_capabilities;
	p->meas_config        = cq_meas_config;
	p->check_mode         = cq_check_mode;
	p->set_mode           = cq_set_mode;
	p->needs_calibration  = cq_needs_calibration;
	p->get_n_a_cals       = cq_get_n_a_cals;
	p->calibrate          = cq_calibrate;
	p->set_uicallback     = cq_set_uicallback;
	p->set_event_callback = cq_set_event_callback;
	p->inst_interp_error  = cq_inst_interp_error;
	p->interp_error       = cq_interp_error;
	p->read_strip         = cq_read_strip;
	p->read_sample        = cq_read_sample;
	p->read_chart         = cq_read_chart;
	p->read_xy            = cq_read_xy;
	p->last_scomerr       = cq_last_scomerr;
	p->del                = cq_del;
	p->dtype              = instI1Pro;
	cq_fake_icom.port_type = cq_icom_port_type;
	cq_fake_icom.port_attr = cq_icom_port_attr;
	p->icom               = &cq_fake_icom;
	p->uicallback         = uicallback;
	p->uic_cntx           = cntx;

	return (inst *)p;
}
