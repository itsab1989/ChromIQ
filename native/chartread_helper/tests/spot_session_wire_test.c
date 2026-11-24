/* spot_session_wire_test: Read single patches' spot session (item 43 steps
 * 2-3, 2026-11-24) and the chart's patch-by-patch reader, BOTH run as the
 * real helper (chromiq_chartread.c compiled with -DCQ_FAKE_USB_TEST and its
 * main renamed cq_helper_main) through the REAL vendored i1Pro 2 driver, on
 * a FAKE USB layer. Nothing here touches real hardware.
 *
 *   spot_session_wire_test <scratch dir> [restored] -- <helper arguments...>
 *
 * The scratch directory is ArgyllCMS's calibration cache for the run
 * (XDG_CACHE_HOME), so nothing is ever written to the person's cache. With
 * "restored", the instrument object is opened the way i1pro_imp_init opens
 * it after an earlier session saved its calibration there
 * (i1pro_restore_calibration): nothing is needed at the start.
 *
 * The helper reads its JSON commands from stdin and writes its events to
 * stdout, as in the app. Every USB request goes to STDERR as one line
 * "WIRE CTL d4 <hex>", "WIRE RD 82 <n>", ... (the format of
 * i1pro2_startcal_test.c), and the close prints the UV state the driver is
 * left in ("WIRE STATE uv_en <n> lit <n>") before ArgyllCMS's own close.
 * tests/test_spot_session_wire.py runs both readers with the same presses
 * and compares the two traces.
 *
 * The fake readings are INVENTED: a flat dark, a flat lamp white, a
 * wavelength-LED peak and a faint UV-LED level; the EEPROM-derived values are
 * invented in the shape of the driver's (no instrument data). With
 * CQ_WIRE_FAIL_AT=<n> the n-th 0xD4 trigger fails as an unplugged
 * instrument's would (a USB error).
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

int cq_helper_main(int argc, char *argv[]);

#define NRAW 128
#define NSEN 134
#define NWAV 36
#define DARK_LEVEL 1000
#define WL_PEAK_RAW 60.3

static int last_flags = -1;
static int d4_count = 0, fail_at = 0, failed = 0;
static int restored = 0;

static void hex(const unsigned char *b, int n) {
	int i;
	for (i = 0; i < n; i++)
		fprintf(stderr, "%02x", b[i]);
}

static int fake_control(icoms *p, int requesttype, int request, int value,
                        int index, unsigned char *rwbuf, int rwsize,
                        int *xferred, double tout) {
	(void)p; (void)value; (void)index; (void)tout;
	if (failed)
		return ICOM_USBW;		/* unplugged: nothing answers any more */
	if ((request & 0xff) == 0xD4 && fail_at > 0 && ++d4_count == fail_at) {
		failed = 1;
		fprintf(stderr, "WIRE D4-FAILED\n");
		fflush(stderr);
		return ICOM_USBW;
	}
	fprintf(stderr, "WIRE CTL %02x ", request & 0xff);
	if ((requesttype & IUSB_ENDPOINT_DIR_MASK) == IUSB_ENDPOINT_OUT)
		hex(rwbuf, rwsize);
	else
		fprintf(stderr, "in%d", rwsize);
	fprintf(stderr, "\n");
	fflush(stderr);
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
	if (failed)
		return ICOM_USBW;
	fprintf(stderr, "WIRE WR %02x ", ep & 0xff);
	hex(wbuf, wsize);
	fprintf(stderr, "\n");
	fflush(stderr);
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
		if ((last_flags & 0xff00) == 0x0100)
			v += 30000;					/* the lamp: flat */
		else if (last_flags == 0x0300) {	/* the wavelength LED: a peak */
			double d = (j - WL_PEAK_RAW) / 4.0;
			v += (int)(20000.0 * exp(-0.5 * d * d));
		} else if ((last_flags & 0xff00) == 0x0200)
			v += 400 + 4 * (j % 7);	/* the UV LED */
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
	if (failed) {
		*bread = 0;
		return ICOM_USBR;
	}
	fprintf(stderr, "WIRE RD %02x %d\n", ep & 0xff, bsize);
	fflush(stderr);
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

static double wlpoly1[4] = { 350.0, 3.1, 0.0, 0.0 };
static double wlpoly2[4] = { 350.0, 3.1, 0.0, 0.0 };
static double led_spec[50];
static double lin_identity[2] = { 0.0, 1.0 };

static void (*real_del)(inst *p) = NULL;

/* the close: the UV state the helper leaves the driver in, then ArgyllCMS's own */
static void traced_del(inst *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = (i1proimp *)p->m;
	if (m != NULL)
		fprintf(stderr, "WIRE STATE uv_en %d lit %d\n", m->uv_en, i1pro2_cq_dual_uv_lit(p));
	fprintf(stderr, "WIRE CLOSE\n");
	fflush(stderr);
	real_del(pp);
}

static inst_code fake_init_coms(inst *pp, baud_rate br, flow_control fc, double tout) {
	(void)br; (void)fc; (void)tout;
	((i1pro *)pp)->gotcoms = 1;
	return inst_ok;
}

/* i1pro_imp_init's state at the end of an open, without the EEPROM read:
 * the per-mode settings of i1pro_imp.c ("Set up the current state of each
 * mode"), invented EEPROM values in their shape */
static inst_code fake_init_inst(inst *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = (i1proimp *)p->m;
	int i, j;

	usb_init_cancel(&m->rd_sync);
	m->capabilities2 = I1PRO_CAP2_WL_LED | I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL;
	m->serno = 987654;
	m->fwrev = 634;
	m->msec = msec_time();
	m->intclkp = m->intclkp2 = 36e-6;
	m->subclkdiv = 340;
	m->subclkdiv2 = 136;
	m->min_int_time = 139 * 36e-6;
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
	m->wl_cal_inttime = 16104 * 36e-6;
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
		m->emis_coef[0][j] = 0.02 * (j < 2 ? 0.15 : (j >= 22 && j < 28 ? 1.5 : 1.0));
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
		s->targmaxitime = 2.0;
		s->targoscale2 = 0.15;
		s->gainmode = 0;
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
		s->idark_int_time[0] = s->idark_int_time[2] = m->min_int_time;
		s->idark_int_time[1] = s->idark_int_time[3] = 4.0;
		s->want_calib = 1;
		s->want_dcalib = 1;
	}
	{	/* i1p_refl_spot (i1pro_imp.c) */
		i1pro_state *s = &m->ms[i1p_refl_spot];
		s->targoscale = 1.0;
		s->reflective = 1;
		s->adaptive = 1;
		s->inttime = 0.02366;
		s->dark_int_time = s->inttime;
		s->dadaptime = 0.10;
		s->wadaptime = 0.10;
		s->lamptime = 0.25;
		s->dcaltime = 0.05;
		s->wcaltime = 0.05;
		s->dreadtime = 0.05;
		s->wreadtime = 0.05;
		s->maxscantime = 0.0;
	}
	{	/* i1p_refl_scan */
		i1pro_state *s = &m->ms[i1p_refl_scan];
		s->reflective = 1;
		s->scan = 1;
		s->adaptive = 1;
		s->inttime = m->min_int_time;
		s->dark_int_time = s->inttime;
		s->targoscale = 0.25;
		s->lamptime = 0.5;
		s->dadaptime = 0.10;
		s->wadaptime = 0.10;
		s->dcaltime = 0.5;
		s->wcaltime = 2.5;
		s->dreadtime = 0.10;
		s->wreadtime = 0.10;
		s->maxscantime = 20.0;
	}
	m->mmode = i1p_refl_spot;
	if (i1pro_compute_wav_filters(p, 0, 0) != I1PRO_OK
	 || i1pro_compute_wav_filters(p, 0, 1) != I1PRO_OK)
		return inst_internal_error;
	if (restored) {			/* as i1pro_imp_init after its EEPROM */
		i1pro_restore_calibration(p);
		if (m->ms[0].wl_valid
		 && (i1pro_compute_wav_filters(p, 0, 0) != I1PRO_OK
		  || i1pro_compute_wav_filters(p, 0, 1) != I1PRO_OK))
			return inst_internal_error;
	}
	p->inited = 1;
	/* THIS FAKE HAS NO HIGH-RESOLUTION TABLES (safety review S2): the stock
	 * high-res setup (i1pro_create_hr) reads EEPROM data invented nowhere
	 * here and crashed at random. So the fake offers no high resolution:
	 * -H is then the request ArgyllCMS drops for an instrument without that
	 * mode, set_mode never builds the tables, and every run is the same. The
	 * session's dual refusal for -H is decided from the flag itself
	 * (cq_ss_conditions), before any capability, so the test still proves
	 * "-H keeps the UV light off". */
	p->cap &= ~inst_mode_highres;
	return inst_ok;
}

inst *cq_test_new_inst(a1log *log, inst_code (*uicallback)(void *cntx, inst_ui_purp purp),
                       void *cntx) {
	static icompath path;
	inst *p;
	memset(&path, 0, sizeof(path));
	path.name = "fake i1Pro 2 (spot_session_wire_test)";
	path.dtype = instI1Pro2;
	path.dctype = icomt_usb | icomt_instrument;
	if ((p = new_inst(&path, 0, log, uicallback, cntx)) == NULL)
		return NULL;
	p->icom->usb_control = fake_control;
	p->icom->usb_write = fake_write;
	p->icom->usb_read = fake_read;
	p->icom->usb_wait_io = fake_wait_io;
	p->icom->usb_cancel_io = fake_cancel_io;
	p->init_coms = fake_init_coms;
	p->init_inst = fake_init_inst;
	real_del = p->del;
	p->del = traced_del;
	return p;
}

int main(int argc, char *argv[]) {
	int i, k;
	char *hargv[64];
	const char *fa;
	if (argc < 3) {
		fprintf(stderr, "usage: spot_session_wire_test <scratch> [restored] -- <helper args>\n");
		return 2;
	}
#ifdef NT
	_putenv_s("XDG_CACHE_HOME", argv[1]);
#else
	setenv("XDG_CACHE_HOME", argv[1], 1);
#endif
	if ((fa = getenv("CQ_WIRE_FAIL_AT")) != NULL)
		fail_at = atoi(fa);
	for (i = 2; i < argc && strcmp(argv[i], "--") != 0; i++)
		if (strcmp(argv[i], "restored") == 0)
			restored = 1;
	k = 0;
	hargv[k++] = "chromiq-chartread";
	for (i++; i < argc && k < 63; i++)
		hargv[k++] = argv[i];
	hargv[k] = NULL;
	return cq_helper_main(k, hargv);
}
