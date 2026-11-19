/* CHROMIQ FILE: the strip shift test (4.3.50). See chromiq_shift.h for what
 * it decides and why; workflow/strip_shift.py is its Python twin, checked
 * against this file number for number (tests/test_strip_shift_c.py).
 *
 * AGPL-3.0 like the rest of ChromIQ's helper code (see License.txt). */
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "chromiq_shift.h"

/* L*a*b* D50 of XYZ 0..100: instlib's sa_XYZ2Lab (sa_conv.c) with sa_D50,
 * the conversion the helper's colour check uses, written out here so the
 * file stands alone. */
static void cqs_lab(const double *xyz, double scale, double *lab) {
	static const double w[3] = { 0.9642, 1.0000, 0.8249 };
	double f[3];
	int j;
	for (j = 0; j < 3; j++) {
		double t = scale * xyz[j] / 100.0 / w[j];
		f[j] = t > 0.008856451586 ? pow(t, 1.0 / 3.0) : 7.787036979 * t + 16.0 / 116.0;
	}
	lab[0] = 116.0 * f[1] - 16.0;
	lab[1] = 500.0 * (f[0] - f[1]);
	lab[2] = 200.0 * (f[1] - f[2]);
}

static double cqs_de(const double *a, const double *b) {
	double d0 = a[0] - b[0], d1 = a[1] - b[1], d2 = a[2] - b[2];
	return sqrt(d0 * d0 + d1 * d1 + d2 * d2);
}

static int cqs_cmp(const void *a, const void *b) {
	double x = *(const double *)a, y = *(const double *)b;
	return x < y ? -1 : x > y ? 1 : 0;
}

int cq_shift_test(const double (*read)[3], const double (*expd)[3], int n,
                  const double paper[3], cq_shift_result *res) {
	double (*lr)[3] = NULL, (*le)[3] = NULL, lp[3], *pd = NULL;
	double sr = 0.0, se = 0.0, yn;
	int i, j, e, k, np;

	memset(res, 0, sizeof(*res));
	res->score = -1e9;
	if (read == NULL || expd == NULL || paper == NULL || n < CQS_NMIN)
		return 0;
	for (i = 0; i < n; i++) {
		sr += read[i][1];
		se += expd[i][1];
	}
	if (!(sr > 1e-6) || !(se > 1e-6))
		return 0;
	yn = se / sr;		/* the colour check's ynorm */

	np = n * (n - 1) / 2;
	lr = malloc(sizeof(*lr) * n);
	le = malloc(sizeof(*le) * n);
	pd = malloc(sizeof(double) * np);
	if (lr == NULL || le == NULL || pd == NULL) {
		free(lr); free(le); free(pd);
		return 0;
	}
	for (i = 0; i < n; i++) {
		cqs_lab(read[i], yn, lr[i]);
		cqs_lab(expd[i], 1.0, le[i]);
	}
	cqs_lab(paper, 1.0, lp);
	for (i = k = 0; i < n; i++)
		for (j = i + 1; j < n; j++)
			pd[k++] = cqs_de(le[i], le[j]);
	qsort(pd, np, sizeof(double), cqs_cmp);
	res->m = np % 2 ? pd[np / 2] : 0.5 * (pd[np / 2 - 1] + pd[np / 2]);

	for (e = 0; e < 2; e++) {
		double a = 0.0, b = 0.0, d = 0.0;
		for (i = 0; i < 3; i++) {
			/* position i from this end; its neighbour towards the end, or paper */
			int ix = e == 0 ? i : n - 1 - i;
			const double *sh = i == 0 ? lp : le[e == 0 ? ix - 1 : ix + 1];
			a += cqs_de(lr[ix], le[ix]);
			b += cqs_de(lr[ix], sh);
			d += cqs_de(le[ix], sh);
			if (i >= 1) {
				int kk = i + 1;		/* 2 or 3 */
				double s = (a - b) / kk, dd = d / kk;
				int ok;
				res->s[e][kk - 2] = s;
				res->d[e][kk - 2] = dd;
				if (s > res->score && !res->flagged)
					res->score = s;
				if (!(res->m > 0.0) || dd < CQS_QMIN * res->m)
					continue;	/* the two explanations cannot be told apart here */
				ok = kk == 3 ? s >= CQS_T3 : (s >= CQS_T2 && s >= CQS_F2 * dd);
				if (ok && (!res->flagged || s > res->score)) {
					res->flagged = 1;
					res->end = e;
					res->k = kk;
					res->score = s;
				}
			}
		}
	}
	/* k = 1, the paper's fingerprint, only when k = 2 / 3 found nothing */
	for (e = 0; e < 2 && !res->flagged; e++) {
		int ix = e == 0 ? 0 : n - 1;
		double raw[3], c, dp;
		cqs_lab(read[ix], 1.0, raw);		/* as read, not Y-normalised */
		c = sqrt(raw[1] * raw[1] + raw[2] * raw[2]);
		dp = cqs_de(le[ix], lp);
		if (raw[0] >= CQS_P_L && c <= CQS_P_C && dp >= CQS_P_D) {
			res->flagged = 1;
			res->end = e;
			res->k = 1;
			res->score = raw[0];
			res->chroma = c;
			res->pd = dp;
		}
	}
	free(lr); free(le); free(pd);
	return res->flagged;
}
