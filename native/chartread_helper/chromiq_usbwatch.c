/* CHROMIQ_EXT: which USB step failed (4.3.36). See chromiq_usbwatch.h.
 *
 * READ-ONLY: every wrapper calls the original entry point with the very same
 * arguments and returns its very result. What it adds is bookkeeping in this
 * process, under a lock, only after the call returned.
 * AGPL-3.0 like the rest of the helper (see ../instlib/License.txt). */
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
#include "insttypes.h"
#include "conv.h"
#include "icoms.h"
#include "chromiq_usbwatch.h"

typedef int (*cq_uw_ctl_fn)(icoms *p, int requesttype, int request, int value,
                            int index, unsigned char *rwbuf, int rwsize,
                            int *xferred, double tout);
typedef int (*cq_uw_rw_fn)(icoms *p, usb_cancelt *cancelt, int ep,
                           unsigned char *buf, int bsize, int *done,
                           double tout);

static amutex_static(cq_uw_lock);
static icoms *cq_uw_ic = NULL;
static int cq_uw_family = 0;
static cq_uw_ctl_fn cq_uw_ctl = NULL;
static cq_uw_rw_fn cq_uw_rd = NULL;
static cq_uw_rw_fn cq_uw_wr = NULL;
static unsigned int cq_uw_t0 = 0;		/* the reading began (msec_time) */
static int cq_uw_triggers = 0;
static unsigned int cq_uw_trig1_at = 0;	/* the reading's first trigger began */
static int cq_uw_count = 0;
static cq_uw_fail cq_uw_kept[CQ_UW_KEEP];
static const char *cq_uw_light = NULL;	/* a string literal of the helper */
static unsigned int cq_uw_light_at = 0;

/* The name of a transfer of this driver. */
static const char *cq_uw_name(int kind, int code) {
	if (cq_uw_family == CQ_UW_I1PRO) {
		if (kind == CQ_UW_CONTROL && (code == 0xC0 || code == 0xD4))
			return "measure_trigger";
		if (kind == CQ_UW_CONTROL && code == 0xD6)
			return "light";
		if (kind == CQ_UW_WRITE && code == 0x03)
			return "light";
		if (kind == CQ_UW_READ && code == 0x82)
			return "measurement_read";
		if (kind == CQ_UW_READ && code == 0x84)
			return "button_read";
		if (kind == CQ_UW_READ && code == 0x85)
			return "ruler_read";
		if (kind == CQ_UW_CONTROL)
			return "control";
	} else if (cq_uw_family == CQ_UW_I1PRO3) {
		if (kind == CQ_UW_CONTROL && (code == 0x22 || code == 0x27))
			return "measure_trigger";
		if (kind == CQ_UW_CONTROL && code == 0x29)
			return "light";
		if (kind == CQ_UW_WRITE && code == 0x02)
			return "light";
		if (kind == CQ_UW_READ && code == 0x81)
			return "measurement_read";
		if (kind == CQ_UW_READ && code == 0x84)
			return "ruler_read";
		if (kind == CQ_UW_READ && code == 0x83)
			return "button_read";
		if (kind == CQ_UW_CONTROL)
			return "control";
	}
	return kind == CQ_UW_WRITE ? "write" : kind == CQ_UW_READ ? "read" : "control";
}

/* A result that is not a failure: OK; a short read (how a scan ends); and
 * the button thread's own waits, which end in a timeout or a cancel all the
 * time without anything being wrong (the i1Pro family's 0x84 and 0x85 are
 * read by threads that wait; so is the i1Pro 3's 0x83). */
static int cq_uw_routine(int kind, int code, int se) {
	if (se == ICOM_OK || se == ICOM_SHORT)
		return 1;
	if (kind == CQ_UW_READ && (se & (ICOM_TO | ICOM_CANC)) != 0
	 && (se & ~(ICOM_TO | ICOM_CANC | ICOM_SHORT)) == 0) {
		if (cq_uw_family == CQ_UW_I1PRO && (code == 0x84 || code == 0x85))
			return 1;
		if (cq_uw_family == CQ_UW_I1PRO3 && code == 0x83)
			return 1;
	}
	return 0;
}

static void cq_uw_note(int kind, int code, int se, int asked, int done,
                       double tout, unsigned int start, unsigned int end) {
	int trig;
	if (kind == CQ_UW_CONTROL
	 && strcmp(cq_uw_name(kind, code), "measure_trigger") == 0) {
		amutex_lock(cq_uw_lock);
		trig = ++cq_uw_triggers;
		if (trig == 1)
			cq_uw_trig1_at = start;
		amutex_unlock(cq_uw_lock);
	} else
		trig = -1;
	if (cq_uw_routine(kind, code, se))
		return;
	amutex_lock(cq_uw_lock);
	if (cq_uw_count < CQ_UW_KEEP) {
		cq_uw_fail *f = &cq_uw_kept[cq_uw_count];
		f->kind = kind;
		f->code = code;
		f->step = cq_uw_name(kind, code);
		f->icom = se;
		f->asked = asked;
		f->done = done;
		f->tout_ms = (int)(tout * 1000.0 + 0.5);
		f->took_ms = (int)(end - start);
		f->at_ms = (int)(end - cq_uw_t0);
		f->trigger_no = trig >= 0 ? trig : cq_uw_triggers;
	}
	cq_uw_count++;
	amutex_unlock(cq_uw_lock);
}

static int cq_uw_control(icoms *p, int requesttype, int request, int value,
                         int index, unsigned char *rwbuf, int rwsize,
                         int *xferred, double tout) {
	unsigned int t = msec_time();
	int se = cq_uw_ctl(p, requesttype, request, value, index, rwbuf, rwsize,
	                   xferred, tout);
	cq_uw_note(CQ_UW_CONTROL, request & 0xff, se, rwsize,
	           xferred != NULL ? *xferred : -1, tout, t, msec_time());
	return se;
}

static int cq_uw_read(icoms *p, usb_cancelt *cancelt, int ep,
                      unsigned char *buf, int bsize, int *done, double tout) {
	unsigned int t = msec_time();
	int se = cq_uw_rd(p, cancelt, ep, buf, bsize, done, tout);
	cq_uw_note(CQ_UW_READ, ep & 0xff, se, bsize, done != NULL ? *done : -1,
	           tout, t, msec_time());
	return se;
}

static int cq_uw_write(icoms *p, usb_cancelt *cancelt, int ep,
                       unsigned char *buf, int bsize, int *done, double tout) {
	unsigned int t = msec_time();
	int se = cq_uw_wr(p, cancelt, ep, buf, bsize, done, tout);
	cq_uw_note(CQ_UW_WRITE, ep & 0xff, se, bsize, done != NULL ? *done : -1,
	           tout, t, msec_time());
	return se;
}

void cq_usbwatch_install(icoms *ic, int family) {
	/* One instrument per helper: a new one replaces the last (which is
	 * gone; the fake-USB tests make one per life). */
	if (ic == NULL || ic->usb_control == cq_uw_control)
		return;			/* already watched: never wrap twice */
	if (ic->usb_control == NULL || ic->usb_read == NULL || ic->usb_write == NULL)
		return;
	cq_uw_family = family;
	cq_uw_ctl = ic->usb_control;
	cq_uw_rd = ic->usb_read;
	cq_uw_wr = ic->usb_write;
	cq_uw_t0 = msec_time();
	cq_uw_ic = ic;
	ic->usb_control = cq_uw_control;
	ic->usb_read = cq_uw_read;
	ic->usb_write = cq_uw_write;
}

void cq_usbwatch_forget(void) {
	icoms *ic = cq_uw_ic;
	if (ic == NULL)
		return;
	/* The originals go back, so nothing calls into a watch that ended. */
	ic->usb_control = cq_uw_ctl;
	ic->usb_read = cq_uw_rd;
	ic->usb_write = cq_uw_wr;
	cq_uw_ic = NULL;
}

void cq_usbwatch_begin(void) {
	amutex_lock(cq_uw_lock);
	cq_uw_t0 = msec_time();
	cq_uw_triggers = 0;
	cq_uw_trig1_at = 0;
	cq_uw_count = 0;
	amutex_unlock(cq_uw_lock);
}

void cq_usbwatch_light(const char *name) {
	amutex_lock(cq_uw_lock);
	cq_uw_light = name;
	cq_uw_light_at = msec_time();
	amutex_unlock(cq_uw_lock);
}

int cq_usbwatch_failures(cq_uw_fail *out, int max, int *nout) {
	int n, i;
	amutex_lock(cq_uw_lock);
	n = cq_uw_count < CQ_UW_KEEP ? cq_uw_count : CQ_UW_KEEP;
	if (n > max)
		n = max;
	for (i = 0; i < n; i++)
		out[i] = cq_uw_kept[i];
	i = cq_uw_count;
	amutex_unlock(cq_uw_lock);
	if (nout != NULL)
		*nout = n;
	return i;
}

static const char *cq_uw_kind(int kind) {
	return kind == CQ_UW_CONTROL ? "control" : kind == CQ_UW_READ ? "read" : "write";
}

void cq_usbwatch_json(char *dst, size_t dstlen) {
	cq_uw_fail f[CQ_UW_KEEP];
	int n = 0, all, i;
	size_t o;
	const char *light;
	unsigned int light_at, trig1_at;
	if (dstlen == 0)
		return;
	dst[0] = '\0';
	if (cq_uw_ic == NULL)
		return;
	all = cq_usbwatch_failures(f, CQ_UW_KEEP, &n);
	amutex_lock(cq_uw_lock);
	light = cq_uw_light;
	light_at = cq_uw_light_at;
	trig1_at = cq_uw_trig1_at;
	amutex_unlock(cq_uw_lock);
	o = (size_t)snprintf(dst, dstlen, ",\"usb_step\":\"%s\",\"usb_failures\":%d,"
	                     "\"usb\":[", n > 0 ? f[0].step : "none", all);
	for (i = 0; i < n && o < dstlen; i++)
		o += (size_t)snprintf(dst + o, dstlen - o,
		        "%s{\"step\":\"%s\",\"kind\":\"%s\",\"code\":\"0x%02X\","
		        "\"icom\":\"0x%06X\",\"bytes\":%d,\"asked\":%d,\"tout_ms\":%d,"
		        "\"took_ms\":%d,\"at_ms\":%d,\"trigger\":%d}",
		        i ? "," : "", f[i].step, cq_uw_kind(f[i].kind), f[i].code,
		        (unsigned int)f[i].icom, f[i].done, f[i].asked, f[i].tout_ms,
		        f[i].took_ms, f[i].at_ms, f[i].trigger_no);
	if (o < dstlen)
		o += (size_t)snprintf(dst + o, dstlen - o, "]");
	/* The last light program, and how long before the reading's first
	 * trigger it was sent (negative: after it; null: no trigger yet). */
	if (o < dstlen && light != NULL) {
		if (trig1_at != 0)
			snprintf(dst + o, dstlen - o,
			         ",\"light\":\"%s\",\"light_to_trigger_ms\":%d",
			         light, (int)(trig1_at - light_at));
		else
			snprintf(dst + o, dstlen - o,
			         ",\"light\":\"%s\",\"light_to_trigger_ms\":null", light);
	}
}
