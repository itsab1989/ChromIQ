/* i1pro2_dual_test: the i1Pro 2 dual scan's instrument part (2026-11-18,
 * step 2) on a FAKE USB layer, through the REAL vendored driver code
 * (native/instlib/cq_i1pro2_dual.h and the hooks in i1pro_imp.c). Nothing
 * here touches real hardware; the processing of the readings is skipped
 * (i1pro2_cq_dual_noproc_for_test), the wire is exactly the driver's.
 *
 * Every USB request is printed as one line (the format of
 * i1pro2_lights_modes_test.c): "<scenario> CTL d4 <14 bytes hex> ..." for a
 * trigger (intclocks, lamp clocks, readings, flags, big endian), "CTL d8 in4"
 * for the UV volts. tests/test_i1pro2_dual_scan_device.py reads the trace and
 * holds it against the shape of X-Rite i1Profiler's recorded dual sessions
 * (tests/data/i1pro2_dual_wire_shape.json: only request codes, flags, clock
 * counts and reading counts, no instrument data).
 *
 * The ruler endpoint 0x85 streams a quadrature code that counts up (the lamp
 * pass, forward) and then down (the UV pass, back); it ends with a short
 * read after a trigger with the "ruler end" flag has been read.
 * AGPL-3.0 like the rest of the helper (see ../../instlib/License.txt). */

#ifdef SALONEINSTLIB
#include "sa_config.h"
#else
#include "aconfig.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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
#include "cq_ruler.h"
#include "cq_dual.h"
#include "chromiq_dualscan.h"

extern int i1pro2_cq_dual_noproc_for_test;

static const char *scn = "?";
static int fail_d4 = 0;			/* the next 0xD4 fails (a USB error) */
static volatile int end_pending = 0;	/* a "ruler end" trigger was sent */
static volatile int stream_over = 0;	/* the 0x85 stream has ended */
static volatile long rsamples = 0;
static volatile int rdir = 1;		/* +1 forward (lamp pass), -1 back (UV pass) */
static volatile long rpos = 0;		/* the count, one step per 7 samples */
static volatile unsigned int end_at = 0;	/* msec_time() the UV scan ends the stream */
static int scan_ms = 0;			/* how long a lit scan lasts (the ruler streams meanwhile) */
static volatile int cancelled = 0;	/* the close cancels a stream still drained */
static const unsigned char quad[4] = { 0, 1, 3, 2 };

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
	if ((request & 0xff) == 0xD4) {
		if (fail_d4) {
			fail_d4 = 0;
			printf("%s D4-FAILED\n", scn);
			return ICOM_USBW;
		}
		if (rwsize >= 14 && (rwbuf[13] & 0x08)) {
			end_pending = 1;	/* the UV pass: back over the strip, then the end */
			rdir = -1;
			end_at = msec_time() + (unsigned int)scan_ms;
		}
		if (rwsize >= 14 && (rwbuf[13] & 0x04))
			rdir = 1;
	}
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

static void started(usb_cancelt *c) {	/* the read began: the trigger may go */
	if (c != NULL) {
		amutex_lock(c->cmtx);
		if (c->state == 0) {
			c->state = 1;
			amutex_unlock(c->condx);
		}
		amutex_unlock(c->cmtx);
	}
}

static int fake_read(icoms *p, usb_cancelt *c, int ep, unsigned char *buf,
                     int bsize, int *bread, double tout) {
	int i;
	(void)p; (void)tout;
	if ((ep & 0xff) == 0x85) {		/* the ruler: not printed (a stream) */
		if (stream_over) {
			*bread = 0;
			return ICOM_SHORT;
		}
		if (cancelled) {
			*bread = 0;
			return ICOM_CANC;
		}
		if (end_pending && (int)(msec_time() - end_at) >= 0) {	/* the "ruler end" scan is over */
			end_pending = 0;
			stream_over = 1;
			*bread = 0;
			return ICOM_SHORT;
		}
		for (i = 0; i < bsize; i++) {
			if (((rsamples + i) % 7) == 0)
				rpos += rdir;
			buf[i] = quad[((rpos % 4) + 4) % 4];
		}
		rsamples += bsize;
		*bread = bsize;
		msec_sleep(bsize * 36 / 4000);	/* a quarter-size chunk time: the end is seen in time */
		return ICOM_OK;
	}
	if ((ep & 0xff) == 0x82) {
		started(c);
		msec_sleep(20);			/* let the trigger thread send first */
	}
	printf("%s RD %02x %d\n", scn, ep & 0xff, bsize);
	fflush(stdout);
	memset(buf, 0, bsize);
	*bread = bsize;
	return ICOM_OK;
}

static int fake_cancel_io(icoms *p, usb_cancelt *c) {
	(void)p; (void)c;
	cancelled = 1;
	return ICOM_OK;
}

static int fake_wait_io(icoms *p, usb_cancelt *c) {
	(void)p;
	amutex_lock(c->condx);
	amutex_unlock(c->condx);
	return ICOM_OK;
}

/* the factory tables: INVENTED numbers in the shape of the EEPROM's */
static double fake_kA[18], fake_kD[18];
static int tables_n = 18;
static double *fake_get_doubles(struct _i1data *d, unsigned int *count, i1key key) {
	(void)d;
	*count = (unsigned int)tables_n;
	if ((int)key == 0x2f77) return tables_n > 0 ? fake_kA : NULL;
	if ((int)key == 0x2f76) return tables_n > 0 ? fake_kD : NULL;
	return NULL;
}
static void fake_data_del(struct _i1data *d) { free(d); }

static i1pro *make(devType dtype, int caps2, int scan) {
	i1pro *p = (i1pro *)calloc(1, sizeof(i1pro));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1proimp *m;
	i1pro_state *s;
	int j;

	ic->usb_control = fake_control;
	ic->usb_write = fake_write;
	ic->usb_read = fake_read;
	ic->usb_wait_io = fake_wait_io;
	ic->usb_cancel_io = fake_cancel_io;
	p->log = new_a1log_d(NULL);
	p->dtype = dtype;
	p->icom = ic;
	p->gotcoms = 1;
	p->inited = 1;
	if (add_i1proimp(p) != I1PRO_OK) {
		fprintf(stderr, "add_i1proimp failed\n");
		exit(2);
	}
	m = (i1proimp *)p->m;
	m->capabilities2 = caps2;
	usb_init_cancel(&m->rd_sync);
	m->mmode = 0;
	s = &m->ms[0];
	s->reflective = 1;
	s->scan = scan;
	s->lamptime = 0.5;
	s->cal_valid = 1;
	s->dark_valid = 1;
	s->inttime = 139 * 36e-6;		/* the scan's integration in every recording */
	s->wreadtime = 0.05;
	m->intclkp = 36e-6;
	m->intclkp2 = 36e-6;
	m->subclkdiv = 340;
	m->subclkdiv2 = 136;
	m->min_int_time = 0.004;
	m->nsen = 134;
	m->msec = msec_time();
	m->fwrev = 634;
	for (j = 0; j < 18; j++) {
		fake_kA[j] = j >= 3 ? 1.0e-4 * (1.0 + 0.05 * j) : 0.0;
		fake_kD[j] = j >= 3 ? 1.6 * fake_kA[j] : 0.0;
	}
	m->data = (struct _i1data *)calloc(1, sizeof(struct _i1data));
	m->data->get_doubles = fake_get_doubles;
	m->data->del = fake_data_del;
	return p;
}

static void step(const char *what) {
	printf("%s STEP %s\n", scn, what);
	fflush(stdout);
}

static void settle(i1pro *p) {
	i1proimp *m = (i1proimp *)p->m;
	amutex_unlock(m->rd_sync.condx);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
}

/* what i1pro_read_patches_1 does around one reading: trigger, then the
 * ruler's finish (the readings themselves are not read here) */
static int reading(i1pro *p, int nummeas, i1p_mmodif mm, int nread) {
	double inttime = ((i1proimp *)p->m)->ms[0].inttime;
	int ev = i1pro_trigger_one_measure(p, nummeas, &inttime, 0, mm);
	settle(p);
	if (ev != I1PRO_OK)
		printf("%s TRIGGER-FAILED %d\n", scn, ev);
	if (mm != i1p_dark_cal && scan_ms > 0)
		msec_sleep(scan_ms);
	i1pro2_cq_ruler_finish(p, nread, ev);
	return ev;
}

static void close_it(i1pro *p) {
	icoms *ic = p->icom;
	a1log *lg = p->log;
	step("close");
	del_i1proimp(p);
	free(p);
	free(ic);
	del_a1log(lg);
	printf("%s END\n", scn);
	fflush(stdout);
}

static void opts(i1pro *p) {
	double kA[36], kD[36];
	int r = i1pro2_cq_dual_options(p, 1, kA, kD);
	printf("%s OPTIONS %d kA3 %.6g kD3 %.6g\n", scn, r, r == 0 ? kA[3] : 0.0, r == 0 ? kD[3] : 0.0);
}

int main(int argc, char *argv[]) {
	i1pro *p;
	(void)argc; (void)argv;
	i1pro2_cq_dual_noproc_for_test = 1;

	/* single scan: the dual scan never switched on: a lamp strip as always */
	scn = "single";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	step("lamp-strip");
	reading(p, 10, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 500);
	close_it(p);

	/* single scan with the option on but no reading armed: the same */
	scn = "single-on";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	opts(p);
	step("lamp-strip");
	reading(p, 10, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 500);
	close_it(p);

	/* (a) the dual calibration on the tile (scan mode) */
	scn = "tile";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	opts(p);
	{
		cq_dual_tile t;
		int ev;
		step("tile");
		ev = i1pro2_cq_dual_tile(p, &t);
		printf("%s TILE ev %d ok %d lamp_clocks %d uv_clocks %d volts %d %d scan %d uv_en %d\n",
		       scn, ev, t.ok, t.lamp_clocks, t.uv_clocks, t.volts_before, t.volts_after,
		       t.mode_scan, ((i1proimp *)p->m)->uv_en);
	}
	close_it(p);

	/* (b) a dual spot (spot mode: the table's, or patch by patch) */
	scn = "spot";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 0);
	((i1proimp *)p->m)->ms[0].inttime = 517 * 36e-6;	/* the table recording's spot exposure */
	opts(p);
	{
		cq_dual_uv u;
		int ev;
		step("lamp-half");
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_SPOT);
		reading(p, 1, i1p_dark_cal, 1);
		reading(p, 1, i1p_norm, 1);
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
		step("uv-half");
		ev = i1pro2_cq_dual_spot_uv(p, &u);
		printf("%s SPOTUV ev %d n %d clocks %d triggers %d volts %d %d uv_en %d lit %d\n", scn, ev,
		       u.n, u.clocks, u.uv_triggers, u.volts_before, u.volts_after,
		       ((i1proimp *)p->m)->uv_en, i1pro2_cq_dual_uv_lit(p));
		free(u.U);
	}
	close_it(p);

	/* (c) a hand dual strip: the lamp pass (ruler start), the UV pass
	 * (ruler end), one ruler stream */
	scn = "strip";
	stream_over = 0; end_pending = 0; rsamples = 0; rdir = 1; rpos = 0;
	scan_ms = 300;
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	opts(p);
	{
		cq_dual_uv u;
		cq_ruler_rec r;
		double **mm;
		double *lp, *up;
		int got, n1 = 40, n2 = 38, i, ok;
		step("lamp-pass");
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
		reading(p, 5, i1p_dark_cal, 5);
		reading(p, 10, i1p_norm, n1);
		printf("%s AFTER-LAMP reader %s count %d\n", scn,
		       ((i1proimp *)p->m)->cq_ruler_th != NULL ? "running" : "stopped",
		       i1pro2_cq_dual_lamp_count(p));
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
		rdir = 0;
		msec_sleep(200);			/* the person turns round (standing still) */
		step("uv-pass");
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_UV);
		printf("%s ARMED-UV uv_en %d\n", scn, ((i1proimp *)p->m)->uv_en);
		reading(p, 5, i1p_dark_cal, 5);
		{	/* i1pro_read_patches_1 picks i1p2_UV itself when uv_en is set */
			i1p_mmodif mod = ((i1proimp *)p->m)->uv_en ? i1p2_UV : i1p_norm;
			reading(p, 10, mod, n2);
		}
		mm = dmatrix(0, n2 - 1, -1, 128);
		(void)i1pro2_cq_dual_readings(p, mm, n2, mm, 1);
		free_dmatrix(mm, 0, n2 - 1, -1, 128);
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
		printf("%s AFTER-UV uv_en %d lit %d\n", scn, ((i1proimp *)p->m)->uv_en,
		       i1pro2_cq_dual_uv_lit(p));
		ok = i1pro2_cq_dual_take_uv(p, &u);
		printf("%s TAKEUV %d n %d triggers %d volts %d %d\n", scn, ok, u.n, u.uv_triggers,
		       u.volts_before, u.volts_after);
		free(u.U);
		memset(&r, 0, sizeof(r));
		got = i1pro2_cq_ruler_take(p, &r);
		printf("%s RULER got %d valid %d ended %d readings %d clocks %d samples %ld nch %d\n",
		       scn, got, r.valid, r.ended, r.readings, r.clocks, r.samples, r.nch);
		lp = (double *)malloc(sizeof(double) * n1);
		up = (double *)malloc(sizeof(double) * n2);
		ok = got && cq_dual_positions(r.first, r.nch, r.ch_gap, r.ch_code, r.samples,
		                              n1, n2, r.clocks > 0 ? r.clocks : 139, lp, up);
		printf("%s POSITIONS %d", scn, ok);
		if (ok) {
			int up_lamp = 1, down_uv = 1;
			for (i = 1; i < n1; i++) if (lp[i] < lp[i - 1]) up_lamp = 0;
			for (i = 1; i < n2; i++) if (up[i] > up[i - 1]) down_uv = 0;
			printf(" lamp %.1f..%.1f rising %d uv %.1f..%.1f falling %d",
			       lp[0], lp[n1 - 1], up_lamp, up[0], up[n2 - 1], down_uv);
			if (!down_uv)
				for (i = 0; i < n2; i++) printf(" %.1f", up[i]);
		}
		printf("\n");
		free(lp);
		free(up);
		cq_ruler_rec_clear(&r);
	}
	scan_ms = 0;
	close_it(p);

	/* (d) the UV LED off again after a failing UV trigger: a paired UV pass
	 * (0x0209, after a lamp pass with "ruler start") whose trigger fails on
	 * the USB; the helper disarms on every way out, the next strip's lamp
	 * pass is a plain lamp scan (the stream of the failed pair is still
	 * drained, so no "ruler start"), and its UV pass may not be asked for. */
	scn = "uv-error";
	stream_over = 0; end_pending = 0; rsamples = 0; rdir = 1; rpos = 0; cancelled = 0;
	scan_ms = 100;
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	opts(p);
	step("lamp-pass");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
	reading(p, 5, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 40);
	printf("%s READY-AFTER-LAMP %d\n", scn, i1pro2_cq_dual_uv_pass_ready(p));
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	step("uv-pass-fails");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_UV);
	fail_d4 = 1;
	reading(p, 10, i1p2_UV, 0);
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);	/* the helper, on every way out */
	printf("%s AFTER uv_en %d lit %d\n", scn, ((i1proimp *)p->m)->uv_en, i1pro2_cq_dual_uv_lit(p));
	end_pending = 0;					/* the failed trigger never ended the stream */
	step("next-lamp-strip");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
	reading(p, 10, ((i1proimp *)p->m)->uv_en ? i1p2_UV : i1p_norm, 40);
	printf("%s READY %d\n", scn, i1pro2_cq_dual_uv_pass_ready(p));
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	scan_ms = 0;
	close_it(p);

	/* (e) safety review 2026-11-18, M2: the UV pass of a lamp pass that
	 * counted no readings in a running stream is never asked for, and if it
	 * were, its trigger (0x0201: UV + scan, no "ruler end", never recorded)
	 * is refused before anything is sent. (1) the lamp pass's trigger fails
	 * (the ruler is given up); (2) a UV pass abandoned with Esc, then the
	 * next strip's lamp pass gets no "ruler start" over the stream still
	 * drained. */
	scn = "uv-unpaired";
	stream_over = 0; end_pending = 0; rsamples = 0; rdir = 1; rpos = 0; cancelled = 0;
	scan_ms = 100;
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	opts(p);
	step("lamp-trigger-fails");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
	reading(p, 5, i1p_dark_cal, 5);
	fail_d4 = 1;
	reading(p, 10, i1p_norm, 0);
	printf("%s READY-1 %d\n", scn, i1pro2_cq_dual_uv_pass_ready(p));
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_UV);	/* what the helper no longer does */
	printf("%s FORCED-1 %d\n", scn, reading(p, 10, i1p2_UV, 0));
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	printf("%s AFTER-1 uv_en %d lit %d\n", scn, ((i1proimp *)p->m)->uv_en, i1pro2_cq_dual_uv_lit(p));
	close_it(p);
	stream_over = 0; end_pending = 0; rsamples = 0; rdir = 1; rpos = 0; cancelled = 0;
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	opts(p);
	step("uv-pass-esc");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
	reading(p, 5, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 40);
	printf("%s READY-2a %d\n", scn, i1pro2_cq_dual_uv_pass_ready(p));
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);	/* Esc: the UV pass never triggered */
	step("next-strip");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
	reading(p, 5, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 40);
	printf("%s READY-2b %d\n", scn, i1pro2_cq_dual_uv_pass_ready(p));
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_UV);	/* what the helper no longer does */
	printf("%s FORCED-2 %d\n", scn, reading(p, 10, i1p2_UV, 0));
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	printf("%s AFTER-2 uv_en %d lit %d\n", scn, ((i1proimp *)p->m)->uv_en, i1pro2_cq_dual_uv_lit(p));
	scan_ms = 0;
	close_it(p);

	/* (f) safety review 2026-11-18, S3: a UV pass longer than 4000 readings
	 * (about 20 s) is refused whole, never half-used */
	scn = "uv-too-long";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED, 1);
	opts(p);
	{
		cq_dual_uv u;
		double **mm;
		int k;
		for (k = 0; k < 2; k++) {
			int n = k == 0 ? 4000 : 4001;
			i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_UV);
			mm = dmatrix(0, n - 1, -1, 128);
			(void)i1pro2_cq_dual_readings(p, mm, n, mm, 1);
			free_dmatrix(mm, 0, n - 1, -1, 128);
			i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
			printf("%s TAKE %d n %d nread %d\n", scn, i1pro2_cq_dual_take_uv(p, &u), u.n, u.nread);
			free(u.U);
		}
	}
	close_it(p);

	/* (h) 4.3.49: a command held while the UV pass is due. The helper armed
	 * the UV pass and its wait was left by a command BEFORE any trigger
	 * (i1pro_imp_measure returns before its dark reading on an abort): the
	 * helper disarms, holds the command and arms the UV pass again. Nothing
	 * goes on the wire for the held wait; the UV pass that follows is the
	 * recorded 0x0209 and closes the stream; the next strip's lamp pass gets
	 * its own "ruler start" and its UV pass may come (M1 / M2 go on). */
	scn = "uv-held";
	stream_over = 0; end_pending = 0; rsamples = 0; rdir = 1; rpos = 0; cancelled = 0;
	scan_ms = 100;
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	opts(p);
	step("lamp-pass");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
	reading(p, 5, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 40);
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	step("uv-wait-left-by-a-command");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_UV);	/* the wait: no trigger */
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);	/* held: the helper disarms */
	printf("%s READY-HELD %d uv_en %d lit %d\n", scn, i1pro2_cq_dual_uv_pass_ready(p),
	       ((i1proimp *)p->m)->uv_en, i1pro2_cq_dual_uv_lit(p));
	step("uv-pass");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_UV);	/* armed again: the same wait */
	reading(p, 5, i1p_dark_cal, 5);
	reading(p, 10, ((i1proimp *)p->m)->uv_en ? i1p2_UV : i1p_norm, 38);
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	{
		cq_ruler_rec r;
		int got;
		memset(&r, 0, sizeof(r));
		got = i1pro2_cq_ruler_take(p, &r);
		printf("%s RULER got %d ended %d reader %s\n", scn, got, r.ended,
		       ((i1proimp *)p->m)->cq_ruler_th != NULL ? "running" : "stopped");
		cq_ruler_rec_clear(&r);
	}
	step("next-strip");
	stream_over = 0; end_pending = 0; rdir = 1;
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
	reading(p, 5, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 40);
	printf("%s READY-NEXT %d\n", scn, i1pro2_cq_dual_uv_pass_ready(p));
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	end_pending = 1; end_at = msec_time();	/* the close ends the stream left for the test */
	scan_ms = 0;
	close_it(p);

	/* (i) 4.3.49: a strip after a calibration that cannot give M1 / M2. The
	 * helper arms nothing (phase OFF): a plain lamp scan, byte for byte the
	 * single scan's requests, no ruler stream, so no UV pass is due. */
	scn = "uncal";
	stream_over = 0; end_pending = 0; rsamples = 0; rdir = 1; rpos = 0; cancelled = 0;
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL, 1);
	opts(p);
	step("lamp-strip");
	i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	reading(p, 10, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 500);
	printf("%s AFTER reader %s ready %d uv_en %d\n", scn,
	       ((i1proimp *)p->m)->cq_ruler_th != NULL ? "running" : "stopped",
	       i1pro2_cq_dual_uv_pass_ready(p), ((i1proimp *)p->m)->uv_en);
	close_it(p);

	/* (g) where it is not offered */
	scn = "refused";
	p = make(instI1Pro2, I1PRO_CAP2_ZEB_RUL, 1);	/* no UV LED */
	opts(p);
	close_it(p);
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED, 1);
	tables_n = 0;								/* no tables */
	opts(p);
	tables_n = 18;
	close_it(p);
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED, 1);
	((i1proimp *)p->m)->highres = 1;			/* high resolution */
	opts(p);
	((i1proimp *)p->m)->highres = 0;
	close_it(p);
	p = make(instI1Pro, I1PRO_CAP2_UV_LED, 1);	/* an i1Pro (Rev A-D) */
	opts(p);
	close_it(p);
	printf("ALL DONE\n");
	return 0;
}
