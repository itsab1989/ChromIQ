/* CHROMIQ_EXT: the X-Rite i1Pro 2 dual scan, the arithmetic (see
 * chromiq_dualscan.h and workflow/dual_scan/model.py). No instrument access.
 * AGPL-3.0 - see ../instlib/License.txt. */
#include <math.h>
#include <stddef.h>
#include "chromiq_dualscan.h"

static int cq_dual_isfinite(double v) {
	return v == v && v - v == 0.0;		/* not NaN, not +-inf */
}

static double cq_dual_wl(const cq_dual_cal *c, int j) {
	if (c->nb <= 1)
		return c->wl_short;
	return c->wl_short + (c->wl_long - c->wl_short) * (double)j / (double)(c->nb - 1);
}

const char *cq_dual_check(const cq_dual_cal *c) {
	int j, any = 0;
	if (c == NULL || c->nb != CQ_DUAL_NB)
		return "no_uv_tables";
	if (!c->have_uv_tile)
		return "no_dual_calibration";
	for (j = 0; j < c->nb; j++) {
		double wl = cq_dual_wl(c, j);
		if (!cq_dual_isfinite(c->kA[j]) || !cq_dual_isfinite(c->kD[j]))
			return "bad_uv_tables";
		if (c->kA[j] < 0.0 || c->kD[j] < 0.0)
			return "bad_uv_tables";
		if (c->kA[j] > 0.0) {
			any = 1;
			if (wl < 410.0 - 1e-6 || wl > 550.0 + 1e-6 || c->kD[j] <= 0.0)
				return "bad_uv_tables";
		} else if (c->kD[j] != 0.0)
			return "bad_uv_tables";
		if (!cq_dual_isfinite(c->W[j]) || !cq_dual_isfinite(c->T[j]) || !cq_dual_isfinite(c->E[j]))
			return "bad_values";
		if (c->W[j] <= 0.0 || c->E[j] <= 0.0)
			return "no_dual_calibration";
	}
	if (!any)
		return "no_uv_tables";
	return NULL;
}

const char *cq_dual_patch(const cq_dual_cal *c, double s, const double *L,
                          const double *U, double *m1, double *m2) {
	int j;
	const char *why;
	if ((why = cq_dual_check(c)) != NULL)
		return why;
	if (!cq_dual_isfinite(s) || s < 0.5 || s > 2.0)
		return "bad_scale";
	for (j = 0; j < c->nb; j++)
		if (!cq_dual_isfinite(L[j]) || !cq_dual_isfinite(U[j]))
			return "bad_values";
	for (j = 0; j < c->nb; j++) {
		double te, ue, den, jj;
		if (c->kA[j] <= 0.0) {
			m1[j] = m2[j] = L[j];
			continue;
		}
		te = c->T[j] / c->W[j] * c->E[j];
		ue = U[j] * c->E[j];
		den = 1.0 - s * c->kA[j] * te;
		if (den <= 0.05)
			return "bad_scale";
		jj = s * c->kA[j] * (ue - te * L[j]) / den;
		m2[j] = L[j] - jj;
		m1[j] = L[j] + (c->kD[j] / c->kA[j] - 1.0) * jj;
	}
	return NULL;
}

const char *cq_dual_cut(int nb, int ncell, const int (*cells)[2],
                        int nlamp, const double *lamp_pos,
                        int nuv, const double *uv_pos, const double *uv,
                        double trim, int min_readings,
                        double *out, int *counts) {
	int k, i, j;
	double lmin, lmax, umin, umax;
	if (nuv <= 0 || uv == NULL)
		return "uv_pass_missing";
	if (nlamp < 2 || lamp_pos == NULL || uv_pos == NULL)
		return "no_ruler";
	lmin = lmax = lamp_pos[0];
	for (i = 0; i < nlamp; i++) {
		if (!cq_dual_isfinite(lamp_pos[i]))
			return "bad_values";
		if (lamp_pos[i] < lmin) lmin = lamp_pos[i];
		if (lamp_pos[i] > lmax) lmax = lamp_pos[i];
	}
	umin = umax = uv_pos[0];
	for (i = 0; i < nuv; i++) {
		if (!cq_dual_isfinite(uv_pos[i]))
			return "bad_values";
		if (uv_pos[i] < umin) umin = uv_pos[i];
		if (uv_pos[i] > umax) umax = uv_pos[i];
	}
	if (lmax - lmin <= 0.0 || umax - umin <= 0.0)
		return "no_ruler";
	if (ncell <= 0)
		return "uv_pass_count";
	for (k = 0; k < ncell; k++) {
		int s = cells[k][0], n = cells[k][1], cnt = 0;
		double a, b, lo, hi, w;
		if (n < 1 || s < 0 || s + n > nlamp)
			return "uv_pass_count";
		a = lamp_pos[s];
		b = lamp_pos[s + n - 1];
		lo = a < b ? a : b;
		hi = a < b ? b : a;
		w = hi - lo;
		for (j = 0; j < nb; j++)
			out[k * nb + j] = 0.0;
		for (i = 0; i < nuv; i++) {
			if (uv_pos[i] >= lo + trim * w && uv_pos[i] <= hi - trim * w) {
				for (j = 0; j < nb; j++)
					out[k * nb + j] += uv[i * nb + j];
				cnt++;
			}
		}
		if (counts != NULL)
			counts[k] = cnt;
		if (cnt < min_readings)
			return "uv_pass_not_aligned";
		for (j = 0; j < nb; j++)
			out[k * nb + j] /= (double)cnt;
	}
	return NULL;
}
