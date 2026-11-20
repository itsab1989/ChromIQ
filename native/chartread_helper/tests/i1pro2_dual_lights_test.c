/* i1pro2_dual_lights_test: the i1Pro 2 lights Beta inside a dual scan
 * (ChromIQ 4.3.52) on a FAKE USB layer, through the REAL vendored driver
 * code (native/instlib/i1pro_imp.c, CHROMIQ PATCH, and cq_i1pro2_dual.h).
 * Nothing here touches real hardware.
 *
 * What it proves (tests/test_i1pro2_dual_blue_and_quiet_time.py reads it):
 *  - the blue "second pass due" (i1pro2_cq_lights_second_pass) puts exactly
 *    the recorded 0xD6 + 702 bytes on 0x03 on the wire, after the lamp pass
 *    and before the return pass's first trigger, and nothing else;
 *  - it is refused (nothing on the wire) with the lights off, without result
 *    signals, outside the return pass's wait, in the lamp pass, once the
 *    button was pressed, in a single scan, and a second time in one wait;
 *  - the user's quiet time (i1pro2_cq_lights_quiet_ms) changes how long the
 *    next trigger waits after a light write, never a byte;
 *  - after the blue alone the next trigger waits the blue's own 370 ms
 *    (CQ_LIGHTS_BLUE_QUIET_MS, 4.3.52 fix round), whatever the user's quiet
 *    time, and after any later write (the OFF_SLOW before a calibration) the
 *    user's quiet time again.
 * Built a second time against ChromIQ 4.3.51's i1pro.c / i1pro_imp.c /
 * i1pro_imp.h (CQ_V4351, the new entries left out): every life that does not
 * ask for anything new must print exactly the same requests there.
 * 4.3.53 (tests/test_instrument_waits.py): built a third time against 4.3.52's
 * driver (CQ_V4352): the 4.3.52 lives and the lamp lives print the same
 * requests and the same waits there; the lives that pass a wait (the blue's
 * own, i1pro2_cq_lights_blue_quiet_set_ms, and ArgyllCMS's lamp wait,
 * i1pro_cq_lamp_off_ms) change only how long a trigger waits. A lamp life
 * prints "<scn> LAMPGAP <ms since the lamp went off>" before each 0xD4.
 *
 * Lines: "<scn> CTL <req> <hex>", "<scn> WR <ep> <len> <sha-free prefix>",
 * "<scn> RD <ep> <n>", "<scn> GAPMS <ms since the last 0x03 write>" before a
 * 0xD4, "<scn> STEP <what>", "<scn> SECOND-PASS <0|1>", and (not in the
 * lives that must match 4.3.51) "<scn> HELD <ms> <after_blue>" for each hold.
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

extern int i1pro2_cq_dual_noproc_for_test;

static const char *scn = "?";
static volatile int end_pending = 0;
static volatile int stream_over = 0;
static volatile long rsamples = 0;
static volatile int rdir = 1;
/* 4.3.53: the direction of every lamp pass's ruler stream: -1 left to right
 * (the sign of all 23 recorded first passes; the default, so every life
 * written before 4.3.53 is a left-to-right pass 1), +1 right to left, 0 no
 * motion (direction not known). The UV pass runs the other way. */
static volatile int lamp_dir = -1;
static volatile long rpos = 0;
static volatile unsigned int end_at = 0;
static int scan_ms = 0;
static volatile int cancelled = 0;
static unsigned int last_wr_end = 0;	/* msec_time() of the last 0x03 write */
static const unsigned char quad[4] = { 0, 1, 3, 2 };
static i1pro *cur = NULL;		/* the instrument of this life (LAMPGAP) */
static int show_lamp = 0;		/* print LAMPGAP (the lamp lives only) */

static void hex(const unsigned char *b, int n) {
	int i;
	for (i = 0; i < n; i++)
		printf("%02x", b[i]);
}

static int fake_control(icoms *p, int requesttype, int request, int value,
                        int index, unsigned char *rwbuf, int rwsize,
                        int *xferred, double tout) {
	(void)p; (void)value; (void)index; (void)tout;
	if ((request & 0xff) == 0xD4 && last_wr_end != 0)
		printf("%s GAPMS %d\n", scn, (int)(msec_time() - last_wr_end));
	if ((request & 0xff) == 0xD4 && show_lamp && cur != NULL)
		printf("%s LAMPGAP %d\n", scn,
		       (int)(msec_time() - ((i1proimp *)cur->m)->llamponoff));
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
	if ((request & 0xff) == 0xD4 && rwsize >= 14) {
		if (rwbuf[13] & 0x08) {
			end_pending = 1;
			rdir = -lamp_dir;
			end_at = msec_time() + (unsigned int)scan_ms;
		}
		if (rwbuf[13] & 0x04)
			rdir = lamp_dir;
	}
	return ICOM_OK;
}

static int fake_write(icoms *p, usb_cancelt *c, int ep, unsigned char *wbuf,
                      int wsize, int *bwritten, double tout) {
	(void)p; (void)c; (void)tout;
	printf("%s WR %02x %d ", scn, ep & 0xff, wsize);
	hex(wbuf, wsize);
	printf("\n");
	fflush(stdout);
	*bwritten = wsize;
	if ((ep & 0xff) == 0x03 && (last_wr_end = msec_time()) == 0)
		last_wr_end = 1;
	return ICOM_OK;
}

static void started(usb_cancelt *c) {
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
		if (end_pending && (int)(msec_time() - end_at) >= 0) {
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
		msec_sleep(bsize * 36 / 4000);
		return ICOM_OK;
	}
	if ((ep & 0xff) == 0x82) {
		started(c);
		msec_sleep(20);
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

static double fake_kA[18], fake_kD[18];
static double *fake_get_doubles(struct _i1data *d, unsigned int *count, i1key key) {
	(void)d;
	*count = 18;
	if ((int)key == 0x2f77) return fake_kA;
	if ((int)key == 0x2f76) return fake_kD;
	return NULL;
}
static void fake_data_del(struct _i1data *d) { free(d); }

static i1pro *make(int caps2) {
	i1pro *p = (i1pro *)calloc(1, sizeof(i1pro));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1proimp *m;
	i1pro_state *s;
	int j;

	stream_over = 0; end_pending = 0; rsamples = 0; rdir = lamp_dir; rpos = 0; cancelled = 0;
	last_wr_end = 0;
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
	m->capabilities2 = caps2;
	usb_init_cancel(&m->rd_sync);
	m->mmode = 0;
	s = &m->ms[0];
	s->reflective = 1;
	s->scan = 1;
	s->lamptime = 0.5;
	s->cal_valid = 1;
	s->dark_valid = 1;
	s->inttime = 139 * 36e-6;
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
	cur = p;
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

/* what read_strip does around one pass (i1pro.c, CHROMIQ PATCH) */
static void pass_begin(i1pro *p) { i1pro2_cq_lights_reading(p, 1); }
static void pass_end(i1pro *p) { i1pro2_cq_lights_after_read(p); }

static void second_pass(i1pro *p) {
#ifndef CQ_V4351
	printf("%s SECOND-PASS %d\n", scn, i1pro2_cq_lights_second_pass(p));
	fflush(stdout);
#else
	(void)p;
#endif
}

static void press(i1pro *p) {	/* the instrument's button (the switch thread counts it) */
	((i1proimp *)p->m)->switch_count++;
}

#ifndef CQ_V4351
static void held(int ms) {	/* the helper's i1pro2_cq_lights_held */
	printf("%s HELD %d %d\n", scn, ms, i1pro2_cq_lights_held_after_blue);
	fflush(stdout);
}
#endif

static void close_it(i1pro *p) {
	icoms *ic = p->icom;
	a1log *lg = p->log;
	step("close");
	(void)i1pro2_cq_lights_end(p);
	end_pending = 1; end_at = msec_time();	/* a stream left running ends with the close */
	del_i1proimp(p);
	free(p);
	free(ic);
	del_a1log(lg);
	cur = NULL;
	printf("%s END\n", scn);
	fflush(stdout);
}

/* One life: open (lights as asked), a dual strip (lamp pass, the return
 * pass's wait with what `wait` asks for, the return pass), the result, a
 * second dual strip without anything in its wait, the close.
 *   lights   0 off, 1 on
 *   signals  the lights' result signals
 *   dual     the dual scan on (else a single scan: no return pass)
 *   wait     0 nothing, 1 the blue, 2 the button first then the blue,
 *            3 the blue twice, 4 the blue asked in the LAMP pass's wait,
 *            5 the blue, then the return pass is left unread and a
 *            calibration follows (its OFF_SLOW is the last write),
 *            6 the blue, then a result write before the press,
 *            7 the blue, the return pass left (Esc), the next strip's lamp pass
 *   quiet    -2 do not set, else i1pro2_cq_lights_quiet_ms */
static void life(const char *name, int lights, int signals, int dual, int wait, int quiet) {
	i1pro *p;
	double kA[36], kD[36];
	scn = name;
	scan_ms = 60;
	p = make(I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL | I1PRO_CAP2_IND_LED);
	/* a whole life at the real 2100 ms would take long: 150 ms, as the other
	 * lights tests; a life about the user's quiet time uses the real path */
	i1pro2_cq_lights_quiet_ms_for_test = quiet == -2 ? 150 : 0;
#ifndef CQ_V4351
	i1pro2_cq_lights_quiet_ms = quiet == -2 ? -1 : quiet;
	i1pro2_cq_lights_held = strncmp(name, "same_", 5) == 0 ? NULL : held;
#else
	(void)quiet;
#endif
	if (dual)
		printf("%s OPTIONS %d\n", scn, i1pro2_cq_dual_options(p, 1, kA, kD));
	if (lights) {
		i1pro2_cq_lights_options(p, signals, 0);
		printf("%s LIGHTS %d\n", scn, i1pro2_cq_lights_begin(p));
	}
	step("lamp-pass");
	pass_begin(p);
	if (dual)
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
	if (wait == 4)
		second_pass(p);
	press(p);
	reading(p, 5, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 40);
	pass_end(p);
	if (dual)
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	if (dual) {
		step("return-wait");
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_UV);
		pass_begin(p);
		if (wait == 2)
			press(p);
		if (wait == 1 || wait == 2 || wait == 3 || wait == 5)
			second_pass(p);
		if (wait == 3)
			second_pass(p);
		if (wait == 6) {	/* a result write after the blue, before the press */
			second_pass(p);
			i1pro2_cq_lights_result(p, 1);
		}
		if (wait == 7) {	/* Esc with the blue showing, then a new strip's lamp pass */
			second_pass(p);
			pass_end(p);
			i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
			step("esc-then-lamp");
			pass_begin(p);
			i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
			press(p);
			reading(p, 5, i1p_dark_cal, 5);
			close_it(p);
			return;
		}
		if (wait == 5) {
			/* the return pass is left (Esc) with the blue showing, then a
			 * calibration: it starts dark (OFF_SLOW), and the quiet time
			 * after that write is the user's again, not the blue's */
			pass_end(p);
			i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
			step("calibration");
			reading(p, 5, i1p_dark_cal, 5);
			close_it(p);
			return;
		}
		if (wait != 2)
			press(p);
		step("return-pass");
		reading(p, 5, i1p_dark_cal, 5);
		reading(p, 10, ((i1proimp *)p->m)->uv_en ? i1p2_UV : i1p_norm, 38);
		pass_end(p);
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
	}
	step("result");
	i1pro2_cq_lights_owe(p);
	i1pro2_cq_lights_result(p, 1);
	if (dual) {
		/* the next strip: the blue is asked for in its lamp pass's wait,
		 * where it never belongs */
		step("next-lamp-pass");
		stream_over = 0; end_pending = 0; rdir = lamp_dir;
		pass_begin(p);
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_LAMP);
		if (wait == 1)
			second_pass(p);
		press(p);
		reading(p, 5, i1p_dark_cal, 5);
		reading(p, 10, i1p_norm, 40);
		pass_end(p);
		i1pro2_cq_dual_arm(p, CQ_DUAL_PHASE_OFF);
		if (wait == 1) {
			/* after the return pass's wait was left: the dual phase is off */
			step("after-the-wait");
			pass_begin(p);
			second_pass(p);
			pass_end(p);
		}
	}
	close_it(p);
}

/* 4.3.53: ArgyllCMS's lamp wait before a dark reading. The lamp went off
 * (llamponoff = now, as i1pro_readmeasurement records it after a lit
 * reading), then a dark reading and a lit one. lamp -2: do not set (and in
 * 4.3.52's driver there is nothing to set), else i1pro_cq_lamp_off_ms. */
static void lamp_life(const char *name, int lamp) {
	i1pro *p;
	scn = name;
	scan_ms = 0;
	p = make(I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL | I1PRO_CAP2_IND_LED);
	i1pro2_cq_lights_quiet_ms_for_test = 150;
#if !defined(CQ_V4351) && !defined(CQ_V4352)
	i1pro_cq_lamp_off_ms = lamp == -2 ? -1 : lamp;
#else
	(void)lamp;
#endif
	show_lamp = 1;
	step("dark");
	((i1proimp *)p->m)->llamponoff = msec_time();
	reading(p, 5, i1p_dark_cal, 5);
	reading(p, 10, i1p_norm, 40);
	show_lamp = 0;
	close_it(p);
#if !defined(CQ_V4351) && !defined(CQ_V4352)
	i1pro_cq_lamp_off_ms = -1;
#endif
}

int main(int argc, char *argv[]) {
	(void)argc; (void)argv;
	i1pro2_cq_dual_noproc_for_test = 1;
	/* the lives that ask for nothing new: the same on 4.3.51's driver */
	life("same_off_single", 0, 0, 0, 0, -2);
	life("same_off_dual", 0, 0, 1, 0, -2);
	life("same_lights_single", 1, 1, 0, 0, -2);
	life("same_lights_dual", 1, 1, 1, 0, -2);
	life("same_ready_dual", 1, 0, 1, 0, -2);
	/* 4.3.53: the lamp wait as ArgyllCMS has it (nothing passed) */
	lamp_life("lamp_default", -2);
#ifndef CQ_V4351
	/* the blue, and where it is refused */
	life("blue_sent", 1, 1, 1, 1, -2);
	life("blue_pressed_first", 1, 1, 1, 2, -2);
	life("blue_twice", 1, 1, 1, 3, -2);
	life("blue_in_lamp_pass", 1, 1, 1, 4, -2);
	life("blue_no_signals", 1, 0, 1, 1, -2);
	life("blue_lights_off", 0, 0, 1, 1, -2);
	life("blue_single_scan", 1, 1, 0, 4, -2);
	/* the user's quiet time: the same requests, another wait */
	life("quiet_0", 1, 1, 1, 1, 0);
	life("quiet_400", 1, 1, 1, 1, 400);
	life("quiet_bad", 1, 1, 1, 1, 99999);	/* out of range: the 2100 ms default */
	/* 4.3.52 fix round: the blue's own quiet time */
	life("quiet_default", 1, 1, 1, 1, -1);	/* the user never set one: 2100 ms, the blue 370 */
	life("blue_then_calibration", 1, 1, 1, 5, 1000);
	/* 4.3.52 release (re-review of the fix round, S1 and S2): the user's wait
	 * wherever the blue is not the last write before the return pass */
	life("blue_then_result", 1, 1, 1, 6, 1000);
	life("esc_then_next_lamp", 1, 1, 1, 7, 1000);
	life("user_wait_single", 1, 1, 0, 0, 1000);	/* dual scan off */
	life("user_wait_ready_dual", 1, 0, 1, 1, 1000);	/* ready light only: no blue */
#endif
#if !defined(CQ_V4351) && !defined(CQ_V4352)
	/* 4.3.53: the waits as values the helper passes. The blue's own wait
	 * (the user's quiet time left at its 2100 ms default) */
	i1pro2_cq_lights_blue_quiet_set_ms = 600;
	life("blue_wait_600", 1, 1, 1, 1, -1);
	i1pro2_cq_lights_blue_quiet_set_ms = 0;
	life("blue_wait_0", 1, 1, 1, 1, -1);
	i1pro2_cq_lights_blue_quiet_set_ms = 99999;	/* out of range: 370 ms */
	life("blue_wait_bad", 1, 1, 1, 1, -1);
	i1pro2_cq_lights_blue_quiet_set_ms = 370;	/* passed at the default */
	life("blue_wait_370", 1, 1, 1, 1, -1);
#if !defined(CQ_V4351) && !defined(CQ_V4352)
	/* 4.3.53: the blue's side follows pass 1's direction (the ruler stream) */
	i1pro2_cq_lights_blue_quiet_set_ms = -1;
	lamp_dir = -1;
	life("blue_side_ltr", 1, 1, 1, 1, -2);		/* left to right: the recorded left blue */
	printf("blue_side_ltr NET %ld %d\n", i1pro2_cq_lights_blue_net, i1pro2_cq_lights_blue_known);
	lamp_dir = 1;
	life("blue_side_rtl", 1, 1, 1, 1, -2);		/* right to left: the right blue */
	printf("blue_side_rtl NET %ld %d\n", i1pro2_cq_lights_blue_net, i1pro2_cq_lights_blue_known);
	lamp_dir = 0;
	life("blue_side_unknown", 1, 1, 1, 1, -2);	/* no motion: not known, the left blue */
	printf("blue_side_unknown NET %ld %d\n", i1pro2_cq_lights_blue_net, i1pro2_cq_lights_blue_known);
	lamp_dir = 1;
	life("blue_side_rtl_lights_off", 0, 0, 1, 1, -2);	/* the lights off: nothing */
	life("blue_side_rtl_single", 1, 1, 0, 4, -2);	/* no dual scan: nothing */
	lamp_dir = -1;
#endif
	i1pro2_cq_lights_blue_quiet_set_ms = -1;
	/* ArgyllCMS's lamp wait */
	lamp_life("lamp_300", 300);
	lamp_life("lamp_0", 0);
	lamp_life("lamp_bad", 99999);			/* out of range: 1500 ms */
	lamp_life("lamp_1500", 1500);			/* passed at the default */
#endif
	printf("ALL DONE\n");
	return 0;
}
