/* CHROMIQ FILE (not ArgyllCMS; scripts/vendor_instlib.py never writes it).
 * The ruler check (Preferences > Beta, 2026-11-14, stage 1: CHECK ONLY).
 *
 * One record per hand-held strip scan of an i1Pro 2 or i1Pro 3, filled by the
 * vendored drivers (i1pro_imp.c, i1pro3_imp.c, CHROMIQ PATCH) only while
 * ChromIQ's helper has armed the ruler for that one read_strip call, and
 * taken by the helper afterwards. Nothing in it is ever fed back into the
 * reading: it is a COPY of what the driver saw.
 *
 * The ruler code stream is kept losslessly and compactly: the first 2-bit
 * code, then for every change of code the gap in samples since the previous
 * change and the new code. A full strip has a few hundred changes.
 *
 * AGPL-3.0 like the rest of ChromIQ's helper code (see License.txt). */
#ifndef CQ_RULER_H
#define CQ_RULER_H

#include <stdlib.h>
#include <string.h>

#define CQ_RULER_MAXCH    20000	/* changes kept per strip */
#define CQ_RULER_MAXPATCH 512	/* patches of today's cut kept */
#define CQ_RULER_MAXTRACE 16384	/* readings / slots of the colour trace kept */

/* How the ruler read ended (i1Pro 2), or where the data came from (i1Pro 3). */
#define CQ_RULER_END_NONE      0	/* nothing recorded */
#define CQ_RULER_END_SHORT     1	/* a short read ended the stream (normal) */
#define CQ_RULER_END_CANCELLED 2	/* still pending at the end: cancelled (as i1Profiler) */
#define CQ_RULER_END_TIMEOUT   3	/* no data within the read's timeout */
#define CQ_RULER_END_ERROR     4	/* a USB error (icom_err) */
#define CQ_RULER_END_NOSTART   5	/* the trigger failed or the thread did not start */
#define CQ_RULER_END_ARGYLL    6	/* i1Pro 3: ArgyllCMS's own 0x84 read */
#define CQ_RULER_END_RUNNING   7	/* the stream had not ended: still drained */

/* Why the ruler was given up for the rest of the session (0 = it was not). */
#define CQ_RULER_GIVEUP_NONE     0
#define CQ_RULER_GIVEUP_ERROR    1	/* the ruler read failed (USB error) */
#define CQ_RULER_GIVEUP_NODATA   2	/* not one byte came */
#define CQ_RULER_GIVEUP_NOTEND   3	/* the stream did not end by itself */
#define CQ_RULER_GIVEUP_MEASFAIL 4	/* the measurement read failed with the bits */
#define CQ_RULER_GIVEUP_RATE     5	/* readings came faster than the clock allows */
#define CQ_RULER_GIVEUP_NOSTART  6	/* the read thread could not start */
#define CQ_RULER_GIVEUP_TIMEOUT  7	/* no data within the read's timeout */

#define CQ_RULER_MAXTRACE_OUT 1000	/* trace points kept (decimated) */

#if defined(__GNUC__) || defined(__clang__)
# define CQ_RULER_UNUSED __attribute__((unused))
#else
# define CQ_RULER_UNUSED
#endif

typedef struct {
	int valid;			/* a record of the last armed scan */
	int gen;			/* 2 = i1Pro 2, 3 = i1Pro 3 */
	int ended;			/* CQ_RULER_END_* */
	int icom_err;
	long samples;		/* ruler samples received */
	long bytes;			/* bytes read on the ruler channel */
	int readings;		/* readings of the scan */
	int clocks;			/* integration clocks per reading */
	double clock_s;		/* one clock, seconds */
	double inttime;		/* one reading, seconds */
	int first;			/* the first code */
	int nch;			/* changes kept */
	long ch_dropped;	/* changes past CQ_RULER_MAXCH */
	int *ch_gap;		/* [nch] samples since the previous change */
	unsigned char *ch_code;	/* [nch] the new code */
	int argyll_used;	/* i1Pro 3: ArgyllCMS placed the patches by the ruler */
	int cut_domain;		/* 0 readings, 1 ArgyllCMS's 0.3 mm slots */
	int ncut;
	int cut_ss[CQ_RULER_MAXPATCH];
	int cut_no[CQ_RULER_MAXPATCH];
	int trace_domain;	/* 0 readings, 1 slots */
	int trace_step;		/* readings (or slots) averaged per trace point */
	int ntrace;
	unsigned short *trace;	/* [ntrace * 3] 0..1000, each band / its maximum */
	int giveup;			/* CQ_RULER_GIVEUP_*: this scan made the driver give up */
	int stream_did_not_end;	/* the stream was still running after the scan */
	int rate_ms;		/* trigger to end of the measurement read, ms */
	int npos;			/* i1Pro 3: ArgyllCMS's position slots */
} cq_ruler_rec;

/* Free what a record owns and clear it. */
CQ_RULER_UNUSED static void cq_ruler_rec_clear(cq_ruler_rec *r) {
	if (r == NULL)
		return;
	free(r->ch_gap);
	free(r->ch_code);
	free(r->trace);
	memset(r, 0, sizeof(*r));
}

/* Append the decoded samples zeb[0..n-1] (values 0..3) to the record's
 * stream; *last_at and *last_code carry the state between calls (start at
 * -1 / -1). Allocation failures only stop the keeping, never the caller. */
CQ_RULER_UNUSED static void cq_ruler_rec_feed(cq_ruler_rec *r, const unsigned char *zeb, long n,
                              long *pos, long *last_at, int *last_code) {
	long i;
	for (i = 0; i < n; i++, (*pos)++) {
		int c = zeb[i] & 3;
		if (*last_code < 0) {
			r->first = c;
			*last_code = c;
			*last_at = *pos;
			continue;
		}
		if (c == *last_code)
			continue;
		if (r->ch_gap == NULL) {
			r->ch_gap = (int *)malloc(sizeof(int) * CQ_RULER_MAXCH);
			r->ch_code = (unsigned char *)malloc(CQ_RULER_MAXCH);
			if (r->ch_gap == NULL || r->ch_code == NULL) {
				free(r->ch_gap); free(r->ch_code);
				r->ch_gap = NULL; r->ch_code = NULL;
				r->ch_dropped++;
				*last_code = c;
				continue;
			}
		}
		if (r->nch < CQ_RULER_MAXCH) {
			r->ch_gap[r->nch] = (int)(*pos - *last_at);
			r->ch_code[r->nch] = (unsigned char)c;
			r->nch++;
		} else
			r->ch_dropped++;
		*last_code = c;
		*last_at = *pos;
	}
	r->samples = *pos;
}

/* The coarse colour trace: per reading (or slot) three wide bands of raw
 * values, each value divided by its own maximum over the strip (maxval[],
 * which ArgyllCMS's recognisers clamp to >= 1), averaged in blocks so at most
 * CQ_RULER_MAXTRACE_OUT points are kept; 0..1000. Read only. */
CQ_RULER_UNUSED static void cq_ruler_rec_trace(cq_ruler_rec *r, double **meas,
                              int n, const double *maxval, int nraw, int domain) {
	static const int band[3][2] = { { 10, 40 }, { 40, 80 }, { 80, 118 } };
	int step, i, b, k, j;
	if (r == NULL || meas == NULL || maxval == NULL || n <= 0 || nraw < 118)
		return;
	free(r->trace);
	r->trace = NULL;
	r->ntrace = 0;
	step = (n + CQ_RULER_MAXTRACE_OUT - 1) / CQ_RULER_MAXTRACE_OUT;
	if (step < 1)
		step = 1;
	if ((r->trace = (unsigned short *)malloc(sizeof(unsigned short) * 3
	                 * ((n + step - 1) / step))) == NULL)
		return;
	for (i = 0; i < n; i += step) {
		for (b = 0; b < 3; b++) {
			double acc = 0.0;
			int cnt = 0;
			for (k = i; k < i + step && k < n; k++) {
				for (j = band[b][0]; j < band[b][1]; j++) {
					double mx = maxval[j] > 0.0 ? maxval[j] : 1.0;
					acc += meas[k][j] / mx;
					cnt++;
				}
			}
			acc = cnt > 0 ? acc / cnt : 0.0;
			if (!(acc > 0.0))		/* also NaN */
				acc = 0.0;
			if (acc > 1.0)
				acc = 1.0;
			r->trace[r->ntrace * 3 + b] = (unsigned short)(acc * 1000.0 + 0.5);
		}
		r->ntrace++;
	}
	r->trace_step = step;
	r->trace_domain = domain;
}

/* Today's cut: one patch (first reading or slot, count), as the recogniser
 * kept it. */
CQ_RULER_UNUSED static void cq_ruler_rec_cut(cq_ruler_rec *r, int pix, int ss,
                                             int no, int domain) {
	if (r == NULL || pix < 0 || pix >= CQ_RULER_MAXPATCH)
		return;
	r->cut_ss[pix] = ss;
	r->cut_no[pix] = no;
	if (pix + 1 > r->ncut)
		r->ncut = pix + 1;
	r->cut_domain = domain;
}

#endif /* CQ_RULER_H */
