/* i1pro2_startcal_test: the i1Pro 2's START-UP calibration (ChromIQ 4.3.58,
 * item 40) through the REAL vendored driver (i1pro_imp_calibrate) on a FAKE
 * USB layer. Nothing here touches real hardware.
 *
 * Three requests, each on a fresh instrument object in the state the driver
 * gives a session at its start (want_calib / want_dcalib set, reflective
 * strip mode, nothing restored):
 *   "normal"     inst_calt_needed: the helper's normal start
 *                (chromiq_chartread.c, the strip branch's else-if)
 *   "dual-4357"  inst_calt_ref_white: the dual branch of 4.3.48 to 4.3.57
 *   "dual"       cq_dual_startup_calt(needed): the dual branch since 4.3.58
 *                (chromiq_dualcal.h, the helper's own function)
 * and after a dual one the dual tile (i1pro2_cq_dual_tile), as
 * cq_dd_after_cal does it.
 *
 * Every USB request is printed as one line, "<scenario> CTL d4 <14 bytes
 * hex>" for a trigger (intclocks, lampclocks, readings, flags; big endian),
 * as in i1pro2_dual_test.c. The fake readings are INVENTED: a flat dark, a
 * flat lamp white and a wavelength-LED peak 0.3 raw bins from the reference,
 * so a wavelength fit shows as a non-zero offset. The EEPROM-derived values
 * are invented in the shape of the driver's (no instrument data).
 *
 * ArgyllCMS saves its calibration to a file after a calibration: argv[1] is
 * the directory used as XDG_CACHE_HOME for that, and the program refuses to
 * run without it, so nothing is ever written to the person's cache.
 * AGPL-3.0 like the rest of the helper (see ../../instlib/License.txt). */

#ifdef SALONEINSTLIB
#include "sa_config.h"
#else
#include "aconfig.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "numsup.h"
#include "rspl1.h"
#include "cgats.h"
#include "xspect.h"
#include "insttypes.h"
#include "conv.h"
#include "icoms.h"
#include "inst.h"
#include "i1pro.h"
#include "i1pro_imp.h"
#include "cq_dual.h"
#include "chromiq_dualscan.h"
#include "chromiq_dualcal.h"

#define NRAW 128
#define NSEN 134
#define NWAV 36
#define DARK_LEVEL 1000
#define WL_PEAK_RAW 60.3		/* the reference peak sits at raw 60 (ref_off 40 + 20) */

static const char *scn = "?";
static int last_flags = -1;		/* the flags of the last 0xD4 trigger */

static void hex(const unsigned char *b, int n) {
	int i;
	for (i = 0; i < n; i++)
		printf("%02x", b[i]);
}

static int fake_control(icoms *p, int requesttype, int request, int value,
                        int index, unsigned char *rwbuf, int rwsize,
                        int *xferred, double tout) {
	(void)p; (void)value; (void)index; (void)tout;
	printf("%s CTL %02x ", scn, request & 0xff);
	if ((requesttype & IUSB_ENDPOINT_DIR_MASK) == IUSB_ENDPOINT_OUT)
		hex(rwbuf, rwsize);
	else
		printf("in%d", rwsize);
	printf("\n");
	fflush(stdout);
	if (xferred != NULL)
		*xferred = rwsize;
	if ((requesttype & IUSB_ENDPOINT_DIR_MASK) != IUSB_ENDPOINT_OUT && rwbuf != NULL) {
		memset(rwbuf, 0, rwsize);
		if ((request & 0xff) == 0xD8 && rwsize >= 4) {	/* invented volts */
			rwbuf[0] = 0x02; rwbuf[1] = 0xd5; rwbuf[2] = 0x02; rwbuf[3] = 0xe1;
		}
	}
	if ((request & 0xff) == 0xD4 && rwsize >= 14)
		last_flags = (rwbuf[12] << 8) | rwbuf[13];
	return ICOM_OK;
}

static int fake_write(icoms *p, usb_cancelt *c, int ep, unsigned char *wbuf,
                      int wsize, int *bwritten, double tout) {
	(void)p; (void)c; (void)tout;
	printf("%s WR %02x ", scn, ep & 0xff);
	hex(wbuf, wsize);
	printf("\n");
	fflush(stdout);
	*bwritten = wsize;
	return ICOM_OK;
}

static void put16(unsigned char *b, int v) {
	if (v < 0) v = 0;
	if (v > 65535) v = 65535;
	b[0] = (unsigned char)(v >> 8);
	b[1] = (unsigned char)(v & 0xff);
}

/* one reading of NSEN values (6 shielded cells, then the 128 raw bins) */
static void fill_reading(unsigned char *b) {
	int j, k, v;
	for (k = 0; k < 6; k++)
		put16(b + 2 * k, DARK_LEVEL);
	for (j = 0; j < NRAW; j++) {
		v = DARK_LEVEL;
		if (last_flags == 0x0100 || (last_flags & 0xff00) == 0x0100)
			v += 30000;					/* the lamp on the tile: flat */
		else if (last_flags == 0x0300) {	/* the wavelength LED: a peak */
			double d = (j - WL_PEAK_RAW) / 4.0;
			v += (int)(20000.0 * exp(-0.5 * d * d));
		} else if ((last_flags & 0xff00) == 0x0200)
			v += 4000;					/* the UV LED on the tile */
		put16(b + 2 * (6 + j), v);
	}
}

static int fake_read(icoms *p, usb_cancelt *c, int ep, unsigned char *buf,
                     int bsize, int *bread, double tout) {
	int i;
	(void)p; (void)tout;
	if ((ep & 0xff) == 0x82 && c != NULL) {	/* the read began: the trigger may go */
		amutex_lock(c->cmtx);
		if (c->state == 0) {
			c->state = 1;
			amutex_unlock(c->condx);
		}
		amutex_unlock(c->cmtx);
		msec_sleep(20);
	}
	printf("%s RD %02x %d\n", scn, ep & 0xff, bsize);
	fflush(stdout);
	memset(buf, 0, bsize);
	if ((ep & 0xff) == 0x82)
		for (i = 0; i + 2 * NSEN <= bsize; i += 2 * NSEN)
			fill_reading(buf + i);
	*bread = bsize;
	return ICOM_OK;
}

static int fake_wait_io(icoms *p, usb_cancelt *c) {
	(void)p;
	amutex_lock(c->condx);
	amutex_unlock(c->condx);
	return ICOM_OK;
}

static int fake_cancel_io(icoms *p, usb_cancelt *c) {
	(void)p; (void)c;
	return ICOM_OK;
}

/* the dual scan's factory tables (0x2f76 / 0x2f77): INVENTED numbers */
static double fake_kA[18], fake_kD[18];
static double *fake_get_doubles(struct _i1data *d, unsigned int *count, i1key key) {
	(void)d;
	*count = 18;
	if ((int)key == 0x2f77) return fake_kA;
	if ((int)key == 0x2f76) return fake_kD;
	return NULL;
}
static void fake_data_del(struct _i1data *d) { free(d); }

static double wlpoly1[4] = { 350.0, 3.1, 0.0, 0.0 };	/* x = 128 - raw: 353 .. 747 nm */
static double wlpoly2[4] = { 350.0, 3.1, 0.0, 0.0 };
static double led_spec[50];
static double lin_identity[2] = { 0.0, 1.0 };	/* linearisation: none */

/* An i1Pro 2 object as i1pro_imp_init() leaves it at the start of a session
 * (the per-mode state of i1pro_imp.c's "Set up the current state of each
 * mode", the reflective strip mode selected), with invented EEPROM values. */
static i1pro *make(void) {
	i1pro *p = (i1pro *)calloc(1, sizeof(i1pro));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1proimp *m;
	int i, j;

	ic->usb_control = fake_control;
	ic->usb_write = fake_write;
	ic->usb_read = fake_read;
	ic->usb_wait_io = fake_wait_io;
	ic->usb_cancel_io = fake_cancel_io;
	p->log = new_a1log_d(NULL);
	p->dtype = instI1Pro2;
	p->icom = ic;
	p->gotcoms = 1;
	p->inited = 1;
	if (add_i1proimp(p) != I1PRO_OK) {
		fprintf(stderr, "add_i1proimp failed\n");
		exit(2);
	}
	m = (i1proimp *)p->m;
	usb_init_cancel(&m->rd_sync);
	m->capabilities2 = I1PRO_CAP2_WL_LED | I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL;
	m->serno = 987654;			/* invented: the calibration file is .i1p_987654.cal */
	m->fwrev = 634;
	m->msec = msec_time();
	m->intclkp = m->intclkp2 = 36e-6;
	m->subclkdiv = 340;
	m->subclkdiv2 = 136;
	m->min_int_time = 139 * 36e-6;	/* the scan exposure of every recording */
	m->max_int_time = 4.5;
	m->nsen = NSEN;
	m->nraw = NRAW;
	m->nwav[0] = NWAV;
	m->nwav[1] = 0;
	m->wl_short[0] = 380.0;
	m->wl_long[0] = 730.0;
	m->highgain = 1.0;
	m->sens_target = 37000;
	m->sens_dark = 1500;
	m->sens_sat0 = 60000;
	m->sens_sat1 = 60000;
	m->maxpve = 0xffff;
	m->nlin0 = m->nlin1 = 2;
	m->lin0 = m->lin1 = lin_identity;
	m->wl_cal_inttime = 16104 * 36e-6;	/* the WL-LED exposure i1Profiler sends too */
	m->wl_cal_min_level = 100.0;
	m->wl_cal_fwhm = 20.0;
	m->wl_cal_fwhm_tol = 1000.0;
	m->wl_err_max = 20.0;
	for (i = 0; i < 50; i++) {
		double d = (i - 20.0) / 4.0;
		led_spec[i] = 1.0 * exp(-0.5 * d * d);
	}
	m->wl_led_spec = led_spec;
	m->wl_led_count = 50;
	m->wl_led_ref_off = 40.0;
	m->wlpoly1 = wlpoly1;
	m->wlpoly2 = wlpoly2;
	m->white_ref[0] = dvectorz(0, NWAV - 1);
	m->emis_coef[0] = dvectorz(0, NWAV - 1);
	for (j = 0; j < NWAV; j++) {
		m->white_ref[0][j] = 1.0;
		/* the shape the white check wants of a lamp (i1pro_check_white_reference1) */
		m->emis_coef[0][j] = j < 2 ? 0.15 : (j >= 22 && j < 28 ? 1.5 : 1.0);
	}
	m->straylight[0] = dmatrixz(0, NWAV - 1, 0, NWAV - 1);
	for (j = 0; j < NWAV; j++)
		m->straylight[0][j][j] = 1.0;
	for (j = 0; j < 18; j++) {
		fake_kA[j] = j >= 3 ? 1.0e-4 * (1.0 + 0.05 * j) : 0.0;
		fake_kD[j] = j >= 3 ? 1.6 * fake_kA[j] : 0.0;
	}
	m->data = (struct _i1data *)calloc(1, sizeof(struct _i1data));
	m->data->get_doubles = fake_get_doubles;
	m->data->del = fake_data_del;

	for (i = 0; i < i1p_no_modes; i++) {
		i1pro_state *s = &m->ms[i];
		s->mode = i;
		s->targoscale = 1.0;
		s->inttime = 0.5;
		s->lamptime = 0.5;
		s->wl_led_off = m->wl_led_ref_off;
		s->dark_data = dvectorz(-1, NRAW - 1);
		s->dark_data2 = dvectorz(-1, NRAW - 1);
		s->dark_data3 = dvectorz(-1, NRAW - 1);
		s->dark_data4 = dvectorz(-1, NRAW - 1);
		s->cal_factor[0] = dvectorz(0, NWAV - 1);
		s->cal_factor[1] = dvectorz(0, 0);
		s->white_data = dvectorz(-1, NRAW - 1);
		s->idark_data = dmatrixz(0, 3, -1, NRAW - 1);
		s->want_calib = 1;		/* as the driver's init: an initial calibration */
		s->want_dcalib = 1;
	}
	/* the reflective strip mode (i1pro_imp.c, case i1p_refl_scan) */
	m->mmode = i1p_refl_scan;
	{
		i1pro_state *s = &m->ms[i1p_refl_scan];
		s->reflective = 1;
		s->scan = 1;
		s->adaptive = 1;
		s->inttime = m->min_int_time;
		s->dark_int_time = s->inttime;
		s->targoscale = 0.25;
		s->lamptime = 0.5;
		s->dcaltime = 0.5;
		s->wcaltime = 2.5;
		s->dreadtime = 0.10;
		s->wreadtime = 0.10;
		s->maxscantime = 20.0;
	}
	/* the factory filters (as the init leaves them without a restored offset) */
	if (i1pro_compute_wav_filters(p, 0, 0) != I1PRO_OK
	 || i1pro_compute_wav_filters(p, 0, 1) != I1PRO_OK) {
		fprintf(stderr, "filters failed\n");
		exit(2);
	}
	return p;
}

static void settle(i1pro *p) {
	i1proimp *m = (i1proimp *)p->m;
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
}

static void step(const char *what) {
	printf("%s STEP %s\n", scn, what);
	fflush(stdout);
}

/* cq_handle_calibrate's loop (chromiq_cal.c) without the prompts: the
 * placement asked for is taken as done, as the person does it */
static int calibrate(i1pro *p, inst_cal_type calt) {
	inst_cal_cond calc = inst_calc_none;
	inst_calc_id_type idtype;
	char id[CALIDLEN];
	int ev, rounds;
	for (rounds = 0; rounds < 4; rounds++) {
		idtype = inst_calc_id_none;
		id[0] = '\0';
		ev = i1pro_imp_calibrate(p, &calt, &calc, &idtype, id);
		settle(p);
		if (ev == I1PRO_CAL_SETUP) {
			printf("%s PLACE calc 0x%x\n", scn, (unsigned)calc);
			step("on-the-tile");
			calc &= inst_calc_cond_mask;
			continue;
		}
		return ev;
	}
	return -1;
}

static void run(const char *name, int mode) {
	i1pro *p;
	i1proimp *m;
	inst_cal_type needed = 0, avail = 0, calt;
	icoms *ic;
	a1log *lg;
	int ev;

	scn = name;
	last_flags = -1;
	p = make();
	m = (i1proimp *)p->m;
	i1pro_imp_get_n_a_cals(p, &needed, &avail);
	if (mode == 0)
		calt = inst_calt_needed;
	else if (mode == 1)
		calt = inst_calt_ref_white;
	else
		calt = cq_dual_startup_calt(needed);
	printf("%s NEEDED 0x%x ASKED 0x%x\n", scn, (unsigned)needed, (unsigned)calt);
	if (mode != 0) {
		double kA[36], kD[36];
		printf("%s OPTIONS %d\n", scn, i1pro2_cq_dual_options(p, 1, kA, kD));
	}
	step("calibrate");
	ev = calibrate(p, calt);
	{
		i1pro_state *s = &m->ms[m->mmode];
		printf("%s CALIBRATED ev 0x%x wl_valid %d wl_offset %.3f dark_valid %d cal_valid %d\n",
		       scn, ev, s->wl_valid, s->wl_led_off - m->wl_led_ref_off, s->dark_valid, s->cal_valid);
	}
	if (mode != 0 && ev == I1PRO_OK) {
		cq_dual_tile t;
		int tev;
		step("dual-tile");
		tev = i1pro2_cq_dual_tile(p, &t);
		settle(p);
		printf("%s TILE ev %d ok %d lamp_clocks %d uv_clocks %d\n", scn, tev, t.ok,
		       t.lamp_clocks, t.uv_clocks);
	}
	step("close");
	ic = p->icom;
	lg = p->log;
	del_i1proimp(p);
	free(p);
	free(ic);
	del_a1log(lg);
	printf("%s END\n", scn);
	fflush(stdout);
}

int main(int argc, char *argv[]) {
	if (argc < 2 || argv[1][0] == '\0') {
		fprintf(stderr, "usage: i1pro2_startcal_test <scratch directory for ArgyllCMS's calibration file>\n");
		return 2;
	}
	/* ArgyllCMS saves its calibration after each one: into the scratch, never the cache */
#ifdef NT
	_putenv_s("XDG_CACHE_HOME", argv[1]);
#else
	setenv("XDG_CACHE_HOME", argv[1], 1);
#endif
	run("normal", 0);
	run("dual-4357", 1);
	run("dual", 2);
	printf("ALL DONE\n");
	return 0;
}
