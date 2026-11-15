/* i1pro3_conditions_test: "X-Rite i1Pro 3: keep M0, M1 and M2 from every
 * scan" (Preferences > Beta, 2026-11-15), through the REAL vendored driver
 * code, with no USB at all (the Beta sends and reads nothing new).
 *
 * 1. ArgyllCMS's own conversion of one patch, i1pro3_comp_refl_value, asked
 *    for ONE condition (what -F n / 5 / u does today) and for all THREE at
 *    once (what the Beta does) on copies of the same samples: every number
 *    must be the same, bit for bit. The state is synthetic (deterministic
 *    pseudo-random tables of the real sizes); the arithmetic is the driver's.
 * 2. The Beta's entry points: off = nothing; armed = the extra pointers;
 *    a reading's record taken once; closed = freed.
 * Prints one line per check; tests/test_i1pro3_conditions_driver.py reads
 * them. AGPL-3.0 like the rest of the helper (see ../../instlib/License.txt). */
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
#include "i1pro3.h"
#include "i1pro3_imp.h"

#define NW 36
#define NS 12		/* even (and odd) samples of one patch */

static unsigned long rs = 12345;
static double rnd(double lo, double hi) {
	rs = rs * 1103515245UL + 12345UL;
	return lo + (hi - lo) * (double)((rs >> 8) & 0xffffff) / (double)0xffffff;
}

static double *vec(double lo, double hi) {
	double *v = dvector(0, NW - 1);
	int i;
	for (i = 0; i < NW; i++)
		v[i] = rnd(lo, hi);
	return v;
}

static i1pro3 *make(void) {
	i1pro3 *p = (i1pro3 *)calloc(1, sizeof(i1pro3));
	i1pro3imp *m;
	i1pro3_state *s;
	int i, j, k, l;
	p->log = new_a1log_d(NULL);
	p->dtype = instI1Pro3;
	p->inited = 1;
	if (add_i1pro3imp(p) != I1PRO3_OK)
		exit(2);
	m = (i1pro3imp *)p->m;
	m->nraw = 128;
	m->nwav[0] = NW;
	m->wl_width[0] = 10.0;
	m->wl_short[0] = 380.0;
	m->wl_long[0] = 730.0;
	m->mmode = 0;
	s = &m->ms[0];
	for (i = 0; i < 2; i++)
		for (j = 0; j < 8; j++)
			for (k = 0; k < 4; k++)
				for (l = 0; l < NW; l++)
					m->ledm_poly[i][j][k][l] = rnd(0.2, 0.4);
	m->straylight[0] = dmatrix(0, NW - 1, 0, NW - 1);
	for (i = 0; i < NW; i++)
		for (j = 0; j < NW; j++)
			m->straylight[0][i][j] = (i == j) ? rnd(0.95, 1.0) : rnd(0.0, 0.002);
	m->white_ref[0] = vec(0.85, 0.95);
	m->emis_coef[0] = vec(0.5, 2.0);
	m->m0_fwa[0] = vec(0.1, 0.6);
	m->m1_fwa[0] = vec(0.2, 0.9);
	m->m2_fwa[0] = vec(0.0, 0.2);
	m->fwa_cal[0] = vec(0.05, 0.3);
	m->fwa_std[0] = vec(0.0, 1.0);
	m->ee_sluv_bl = 0.4;
	for (i = 0; i < 2; i++) {
		for (j = 0; j < NW; j++)
			s->calsp_ledm[i][j] = rnd(1.5, 2.5);
		s->calsp_illcr[0][i] = vec(0.9, 1.1);
	}
	s->iavg2aillum[0] = vec(0.4, 0.6);
	s->sc_calsp_nn_white[0] = vec(80.0, 120.0);
	s->cal_l_uv_diff[0] = vec(0.01, 0.05);
	s->cal_s_uv_diff[0] = vec(0.01, 0.05);
	s->reflective = 1;
	return p;
}

/* nsamp samples of NW bands plus the 9 auxiliary values in front */
static double **samples(int even) {
	double **a = dmatrix(0, NS - 1, -9, NW - 1);
	int i, j;
	for (i = 0; i < NS; i++)
		for (j = -9; j < NW; j++)
			a[i][j] = j < 0 ? rnd(0.5, 1.5) : rnd(20.0, 60.0) + (even ? 0.0 : rnd(40.0, 80.0));
	return a;
}

static double **copy(double **a) {
	double **b = dmatrix(0, NS - 1, -9, NW - 1);
	copy_dmatrix(b, a, 0, NS - 1, -9, NW - 1);
	return b;
}

static int same(const double *a, const double *b) {
	return memcmp(a, b, sizeof(double) * NW) == 0;
}

int main(void) {
	i1pro3 *p = make();
	i1pro3imp *m = (i1pro3imp *)p->m;
	int patch, ok_all = 1;
	double one[3][NW], all[3][NW];

	/* 1. bit for bit, on five patches of different samples */
	for (patch = 0; patch < 5; patch++) {
		double **e = samples(1), **o = samples(0);
		double **e1, **o1;
		int c, ok;
		for (c = 0; c < 3; c++) {
			e1 = copy(e); o1 = copy(o);
			memset(one[c], 0, sizeof(one[c]));
			if (i1pro3_comp_refl_value(p, c == 0 ? one[0] : NULL,
			        c == 1 ? one[1] : NULL, c == 2 ? one[2] : NULL,
			        e1, NS, o1, NS, 0) != I1PRO3_OK) {
				printf("patch %d cond %d CONVERT FAILED\n", patch, c);
				return 1;
			}
			free_dmatrix(e1, 0, NS - 1, -9, NW - 1);
			free_dmatrix(o1, 0, NS - 1, -9, NW - 1);
		}
		e1 = copy(e); o1 = copy(o);
		if (i1pro3_comp_refl_value(p, all[0], all[1], all[2], e1, NS, o1, NS, 0)
		        != I1PRO3_OK) {
			printf("patch %d all CONVERT FAILED\n", patch);
			return 1;
		}
		ok = same(one[0], all[0]) && same(one[1], all[1]) && same(one[2], all[2]);
		/* and the three are not trivially equal to each other */
		printf("patch %d BITS %s m0[20]=%.9g m1[20]=%.9g m2[20]=%.9g distinct=%d\n",
		       patch, ok ? "SAME" : "DIFFERENT", all[0][20], all[1][20], all[2][20],
		       !same(all[0], all[1]) && !same(all[1], all[2]));
		ok_all &= ok;
		free_dmatrix(e1, 0, NS - 1, -9, NW - 1);
		free_dmatrix(o1, 0, NS - 1, -9, NW - 1);
		free_dmatrix(e, 0, NS - 1, -9, NW - 1);
		free_dmatrix(o, 0, NS - 1, -9, NW - 1);
	}
	printf("BITS %s\n", ok_all ? "ALL SAME" : "SOME DIFFERENT");

	/* 2. the entry points */
	{
		double row[NW], *m0 = NULL, *m1 = NULL, *m2 = NULL;
		ipatch out[2];
		m->filt = inst_opt_filter_none;
		m1 = NULL;
		m0 = row;
		i1pro3_cq_cond_ptrs(p, 0, &m0, &m1, &m2);
		printf("off PTRS m0=%s m1=%s m2=%s\n", m0 == row ? "main" : m0 ? "extra" : "null",
		       m1 ? "extra" : "null", m2 ? "extra" : "null");
		printf("off TAKE %d\n", i1pro3_cq_cond_take(p, 1, out, 1));
		printf("on OPTIONS %d\n", i1pro3_cq_cond_options(p, 1));
		i1pro3_cq_cond_arm(p, 1);
		printf("armed BEGIN %d\n", i1pro3_cq_cond_begin(p, 2, 0));
		m0 = row; m1 = NULL; m2 = NULL;
		i1pro3_cq_cond_ptrs(p, 1, &m0, &m1, &m2);
		printf("armed PTRS m0=%s m1=%s m2=%s\n", m0 == row ? "main" : m0 ? "extra" : "null",
		       m1 ? "extra" : "null", m2 ? "extra" : "null");
		printf("armed TAKE_BEFORE_FINISH %d\n", i1pro3_cq_cond_take(p, 1, out, 2));
		m->filt = inst_opt_filter_pol;
		printf("pol BEGIN %d\n", i1pro3_cq_cond_begin(p, 2, 0));
		m->filt = inst_opt_filter_none;
		i1pro3_cq_cond_arm(p, 0);
		printf("disarmed BEGIN %d\n", i1pro3_cq_cond_begin(p, 2, 0));
		i1pro3_cq_cond_close(p);
		printf("closed TAKE %d\n", i1pro3_cq_cond_take(p, 1, out, 2));
	}
	printf("ALL DONE\n");
	return ok_all ? 0 : 1;
}
