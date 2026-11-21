/* The i1Pro 2 dual scan's arithmetic in C (chromiq_dualscan.c), on the SAME
 * invented instrument as tests/test_i1pro2_dual_scan_model.py. Prints every
 * number with %.17g; tests/test_i1pro2_dual_scan_engine.py computes the same
 * with workflow/dual_scan in Python and compares. No instrument, no USB.
 * AGPL-3.0 - see ../../instlib/License.txt. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "chromiq_dualscan.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static void invented(cq_dual_cal *c) {
	int j;
	memset(c, 0, sizeof(*c));
	c->nb = CQ_DUAL_NB;
	c->wl_short = 380.0;
	c->wl_long = 730.0;
	c->have_uv_tile = 1;
	for (j = 0; j < CQ_DUAL_NB; j++) {
		double wl = 380.0 + 10.0 * j, x = (wl - 410.0) / 140.0;
		int band = wl >= 410.0 && wl <= 550.0;
		c->kA[j] = band ? 1.2e-4 * (1.0 + 0.8 * sin(M_PI * x)) : 0.0;
		c->kD[j] = band ? c->kA[j] * (1.6 + 0.9 * x) : 0.0;
		c->W[j] = 0.9 + 0.02 * cos(wl / 50.0);
		c->T[j] = 0.012 * exp(-(wl - 380.0) / 25.0) + 1e-4;
		c->E[j] = 2.4e4 * (1.0 + 0.3 * (wl - 380.0) / 350.0);
	}
}

static void patch(int p, double *L, double *U) {
	int j;
	for (j = 0; j < CQ_DUAL_NB; j++) {
		double wl = 380.0 + 10.0 * j;
		L[j] = 0.1 + 0.15 * p + 0.001 * j;
		U[j] = 0.0005 * (p + 1) * exp(-0.5 * pow((wl - 440.0) / 25.0, 2.0))
		     + 0.012 * exp(-(wl - 380.0) / 25.0) * L[j];
	}
}

/* The pairing check (safety review 2026-11-18, M1) on cases from a file named
 * by CQ_DUAL_PAIRING_CASES (tests/test_i1pro2_dual_scan_pairing_c.py writes
 * it): per case "case <name> <n>", then lines "W", "T", "E" and n lines "L",
 * n lines "U" of 36 numbers each; the tables are the invented ones. Prints
 * "pairing <name> <ok|reason> <checked> <usable> <patches> <corr> <err>". */
static int read_vec(FILE *f, const char *tag, double *v) {
	char t[8];
	int j;
	if (fscanf(f, "%7s", t) != 1 || strcmp(t, tag) != 0)
		return 0;
	for (j = 0; j < CQ_DUAL_NB; j++)
		if (fscanf(f, "%lf", &v[j]) != 1)
			return 0;
	return 1;
}

static void pairing_cases(const char *path) {
	FILE *f = fopen(path, "r");
	char kw[16], name[128];
	int n, i;
	if (f == NULL) {
		printf("pairing_cases unreadable\n");
		return;
	}
	while (fscanf(f, "%15s %127s %d", kw, name, &n) == 3 && strcmp(kw, "case") == 0 && n > 0) {
		cq_dual_cal c;
		cq_dual_pairing_ev ev;
		double *L = (double *)malloc(sizeof(double) * CQ_DUAL_NB * (size_t)n);
		double *U = (double *)malloc(sizeof(double) * CQ_DUAL_NB * (size_t)n);
		const char *why;
		int ok = L != NULL && U != NULL;
		invented(&c);
		ok = ok && read_vec(f, "W", c.W) && read_vec(f, "T", c.T) && read_vec(f, "E", c.E);
		for (i = 0; ok && i < n; i++)
			ok = read_vec(f, "L", L + i * CQ_DUAL_NB);
		for (i = 0; ok && i < n; i++)
			ok = read_vec(f, "U", U + i * CQ_DUAL_NB);
		if (!ok) {
			printf("pairing %s unreadable\n", name);
			free(L);
			free(U);
			break;
		}
		why = cq_dual_pairing(&c, n, L, U, &ev);
		printf("pairing %s %s %d %d %d %.17g %.17g\n", name, why == NULL ? "ok" : why, ev.checked,
		       ev.usable, ev.patches, ev.correlation, ev.median_ratio_error);
		free(L);
		free(U);
	}
	fclose(f);
}

/* The cut (after 4.3.54: the whole span less CQ_DUAL_EDGE_STEPS) on cases
 * from a file named by CQ_DUAL_CUT_CASES (tests/test_uv_pass_rule.py writes
 * it): per case "cut <name> <ncell> <nlamp> <nuv>", then "C" and 2 x ncell
 * ints (first reading, count), "P" and nlamp lamp positions, "Q" and nuv UV
 * positions, then nuv lines "U" of 36 numbers. Prints "cutcase <name>
 * <ok|reason> <flatness> <window flatness> <counts...> | <the first band of each patch>". */
static int read_n(FILE *f, const char *tag, double *v, int n) {
	char t[8];
	int j;
	if (fscanf(f, "%7s", t) != 1 || strcmp(t, tag) != 0)
		return 0;
	for (j = 0; j < n; j++)
		if (fscanf(f, "%lf", &v[j]) != 1)
			return 0;
	return 1;
}

static void cut_cases(const char *path) {
	FILE *f = fopen(path, "r");
	char kw[16], name[128];
	int nc, nl, nu, i, k;
	if (f == NULL) {
		printf("cut_cases unreadable\n");
		return;
	}
	while (fscanf(f, "%15s %127s %d %d %d", kw, name, &nc, &nl, &nu) == 5 && strcmp(kw, "cut") == 0
	       && nc > 0 && nl > 0 && nu > 0) {
		int (*cells)[2] = malloc(sizeof(int) * 2 * (size_t)nc);
		int *counts = malloc(sizeof(int) * (size_t)nc);
		double *cv = malloc(sizeof(double) * 2 * (size_t)nc);
		double *lp = malloc(sizeof(double) * (size_t)nl), *up = malloc(sizeof(double) * (size_t)nu);
		double *uv = malloc(sizeof(double) * CQ_DUAL_NB * (size_t)nu);
		double *out = malloc(sizeof(double) * CQ_DUAL_NB * (size_t)nc);
		const char *why;
		int ok = cells && counts && cv && lp && up && uv && out;
		ok = ok && read_n(f, "C", cv, 2 * nc) && read_n(f, "P", lp, nl) && read_n(f, "Q", up, nu);
		for (i = 0; ok && i < nu; i++)
			ok = read_vec(f, "U", uv + i * CQ_DUAL_NB);
		if (!ok) {
			printf("cutcase %s unreadable\n", name);
			break;
		}
		for (k = 0; k < nc; k++) {
			cells[k][0] = (int)cv[2 * k];
			cells[k][1] = (int)cv[2 * k + 1];
		}
		for (k = 0; k < nc; k++)
			counts[k] = -1;
		why = cq_dual_cut(CQ_DUAL_NB, nc, (const int (*)[2])cells, nl, lp, nu, up, uv,
		                  CQ_DUAL_TRIM, CQ_DUAL_MIN_UV, CQ_DUAL_EDGE_STEPS, out, counts);
		printf("cutcase %s %s %.17g %.17g", name, why == NULL ? "ok" : why,
		       cq_dual_flatness(CQ_DUAL_NB, nc, (const int (*)[2])cells, lp, nu, up, uv, CQ_DUAL_TRIM),
		       cq_dual_window_flatness(CQ_DUAL_NB, nc, (const int (*)[2])cells, lp, nu, up, uv,
		                               CQ_DUAL_EDGE_STEPS));
		for (k = 0; k < nc; k++)
			printf(" %d", counts[k]);
		printf(" |");
		for (k = 0; k < nc; k++)
			printf(" %.17g", counts[k] > 0 ? out[k * CQ_DUAL_NB] : 0.0);
		printf("\n");
		free(cells); free(counts); free(cv); free(lp); free(up); free(uv); free(out);
	}
	fclose(f);
}

int main(void) {
	cq_dual_cal c;
	double L[CQ_DUAL_NB], U[CQ_DUAL_NB], m1[CQ_DUAL_NB], m2[CQ_DUAL_NB];
	int p, j;
	const char *why;

	invented(&c);
	printf("check %s\n", cq_dual_check(&c) == NULL ? "ok" : cq_dual_check(&c));
	for (p = 0; p < 5; p++) {
		patch(p, L, U);
		why = cq_dual_patch(&c, 1.137, L, U, m1, m2);
		printf("patch %d %s", p, why == NULL ? "ok" : why);
		for (j = 0; j < CQ_DUAL_NB; j++)
			printf(" %.17g", m1[j]);
		for (j = 0; j < CQ_DUAL_NB; j++)
			printf(" %.17g", m2[j]);
		printf("\n");
	}
	/* refusals */
	patch(0, L, U);
	printf("scale_nan %s\n", cq_dual_patch(&c, NAN, L, U, m1, m2));
	printf("scale_big %s\n", cq_dual_patch(&c, 5.0, L, U, m1, m2));
	c.have_uv_tile = 0;
	printf("no_uv_tile %s\n", cq_dual_patch(&c, 1.1, L, U, m1, m2));
	c.have_uv_tile = 1;
	c.kA[0] = 1e-4;
	printf("table_out_of_band %s\n", cq_dual_check(&c));
	invented(&c);
	memset(c.kA, 0, sizeof(c.kA));
	memset(c.kD, 0, sizeof(c.kD));
	printf("no_tables %s\n", cq_dual_check(&c));
	invented(&c);
	L[3] = NAN;
	printf("nan_value %s\n", cq_dual_patch(&c, 1.1, L, U, m1, m2));
	/* review 2026-11-18 S2: the UV LED did not light at calibration */
	invented(&c);
	for (j = 0; j < CQ_DUAL_NB; j++)
		c.T[j] *= 0.001;
	printf("tile_dark %s\n", cq_dual_check(&c));
	invented(&c);

	/* the cut: 12 patches of 10 lamp readings, a UV pass of 6 per patch back */
	{
		int cells[12][2], counts[12], k, nl = 120, nu = 72;
		double lp[120], up[72], uv[72 * CQ_DUAL_NB], out[12 * CQ_DUAL_NB];
		for (k = 0; k < 12; k++) { cells[k][0] = k * 10; cells[k][1] = 10; }
		for (k = 0; k < nl; k++) lp[k] = k * 7.0;
		for (k = 0; k < nu; k++) {
			int pp;
			up[k] = (nu - 1 - k + 0.5) * (70.0 / 6.0);
			pp = (int)(up[k] / 70.0);
			if (pp > 11) pp = 11;
			for (j = 0; j < CQ_DUAL_NB; j++) uv[k * CQ_DUAL_NB + j] = pp + 1.0;
		}
		why = cq_dual_cut(CQ_DUAL_NB, 12, (const int (*)[2])cells, nl, lp, nu, up, uv,
		                  CQ_DUAL_TRIM, CQ_DUAL_MIN_UV, CQ_DUAL_EDGE_STEPS, out, counts);
		printf("cut %s", why == NULL ? "ok" : why);
		for (k = 0; k < 12; k++) printf(" %.17g:%d", out[k * CQ_DUAL_NB], counts[k]);
		printf("\n");
		/* the second pass stopped half way */
		why = cq_dual_cut(CQ_DUAL_NB, 12, (const int (*)[2])cells, nl, lp, 36, up, uv,
		                  CQ_DUAL_TRIM, CQ_DUAL_MIN_UV, CQ_DUAL_EDGE_STEPS, out, counts);
		printf("cut_half %s\n", why == NULL ? "ok" : why);
		for (k = 0; k < nu; k++) up[k] = 0.0;
		why = cq_dual_cut(CQ_DUAL_NB, 12, (const int (*)[2])cells, nl, lp, nu, up, uv,
		                  CQ_DUAL_TRIM, CQ_DUAL_MIN_UV, CQ_DUAL_EDGE_STEPS, out, counts);
		printf("cut_no_ruler %s\n", why == NULL ? "ok" : why);
		/* review 2026-11-18 S3: the alignment measure and its gate. A
		 * little invented noise inside each cell; then the same pass half a
		 * pitch off (the instrument lifted between the passes). */
		for (k = 0; k < nu; k++) {
			int pp;
			up[k] = (nu - 1 - k + 0.5) * (70.0 / 6.0);
			pp = (int)(up[k] / 70.0);
			if (pp > 11) pp = 11;
			for (j = 0; j < CQ_DUAL_NB; j++)
				uv[k * CQ_DUAL_NB + j] = (pp % 2 ? 3.0 : 1.0) + 0.5 * pp + 0.01 * sin(k * 1.7 + j);
		}
		printf("flat %.17g\n", cq_dual_flatness(CQ_DUAL_NB, 12, (const int (*)[2])cells, lp, nu, up, uv,
		                                        CQ_DUAL_TRIM));
		why = cq_dual_cut(CQ_DUAL_NB, 12, (const int (*)[2])cells, nl, lp, nu, up, uv,
		                  CQ_DUAL_TRIM, CQ_DUAL_MIN_UV, CQ_DUAL_EDGE_STEPS, out, counts);
		printf("cut_aligned %s\n", why == NULL ? "ok" : why);
		for (k = 0; k < nu; k++) {	/* what is under the aperture is half a pitch on */
			int pp = (int)((up[k] + 35.0) / 70.0);
			if (pp > 11) pp = 11;
			for (j = 0; j < CQ_DUAL_NB; j++)
				uv[k * CQ_DUAL_NB + j] = (pp % 2 ? 3.0 : 1.0) + 0.5 * pp + 0.01 * sin(k * 1.7 + j);
		}
		printf("flat_half %.17g\n", cq_dual_flatness(CQ_DUAL_NB, 12, (const int (*)[2])cells, lp, nu, up, uv,
		                                             CQ_DUAL_TRIM));
		why = cq_dual_cut(CQ_DUAL_NB, 12, (const int (*)[2])cells, nl, lp, nu, up, uv,
		                  CQ_DUAL_TRIM, CQ_DUAL_MIN_UV, CQ_DUAL_EDGE_STEPS, out, counts);
		printf("cut_half_pitch %s\n", why == NULL ? "ok" : why);
	}
	if (getenv("CQ_DUAL_PAIRING_CASES") != NULL)
		pairing_cases(getenv("CQ_DUAL_PAIRING_CASES"));
	if (getenv("CQ_DUAL_CUT_CASES") != NULL)
		cut_cases(getenv("CQ_DUAL_CUT_CASES"));
	printf("edge_steps %.17g trim %.17g min_uv %d max_edge_flatness %.17g\n", (double)CQ_DUAL_EDGE_STEPS,
	       (double)CQ_DUAL_TRIM, CQ_DUAL_MIN_UV, (double)CQ_DUAL_MAX_EDGE_FLATNESS);
	printf("ALL DONE\n");
	return 0;
}
