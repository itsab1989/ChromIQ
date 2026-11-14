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
	int ntrace;
	unsigned short *trace;	/* [ntrace * 3] 0..1000, each band / its maximum */
} cq_ruler_rec;

/* Free what a record owns and clear it. */
static void cq_ruler_rec_clear(cq_ruler_rec *r) {
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
static void cq_ruler_rec_feed(cq_ruler_rec *r, const unsigned char *zeb, long n,
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

#endif /* CQ_RULER_H */
