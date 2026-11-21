/* CHROMIQ_EXT: the X-Rite i1Pro 2 dual scan, the arithmetic (see
 * chromiq_dualscan.h and workflow/dual_scan/model.py). No instrument access.
 * AGPL-3.0 - see ../instlib/License.txt. */
#include <math.h>
#include <stddef.h>
#include <stdlib.h>
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
	/* the UV LED lit at calibration: Te = T / W * E over 380-410 nm
	 * (model.py MIN_UV_TILE_TE, from the two recorded instruments) */
	{
		double sum = 0.0;
		int n = 0;
		for (j = 0; j < c->nb; j++) {
			double wl = cq_dual_wl(c, j);
			if (wl >= CQ_DUAL_TILE_LO - 1e-6 && wl <= CQ_DUAL_TILE_HI + 1e-6) {
				sum += c->T[j] / c->W[j] * c->E[j];
				n++;
			}
		}
		if (!(n > 0 && sum / (double)n >= CQ_DUAL_MIN_TILE_TE))
			return "uv_tile_dark";
	}
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

#define CQ_DUAL_MAXCELL 1024
static int cq_cnt_tmp[CQ_DUAL_MAXCELL];

const char *cq_dual_cut(int nb, int ncell, const int (*cells)[2],
                        int nlamp, const double *lamp_pos,
                        int nuv, const double *uv_pos, const double *uv,
                        double trim, int min_readings, double edge,
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
	if (ncell <= 0 || ncell > CQ_DUAL_MAXCELL)
		return "uv_pass_count";
	for (k = 0; k < ncell; k++) {
		int s = cells[k][0], n = cells[k][1], cnt = 0;
		double a, b, lo, hi;
		if (n < 1 || s < 0 || s + n > nlamp)
			return "uv_pass_count";
		a = lamp_pos[s];
		b = lamp_pos[s + n - 1];
		lo = a < b ? a : b;
		hi = a < b ? b : a;
		for (j = 0; j < nb; j++)
			out[k * nb + j] = 0.0;
		/* the whole span less *edge* ruler steps at each end (header); *edge* < 0: the
		 * central part (*trim* at each end), 4.3.54's window, for a pass that could not
		 * be lined up */
		for (i = 0; i < nuv; i++) {
			double wlo = edge >= 0.0 ? lo + edge : lo + trim * (hi - lo);
			double whi = edge >= 0.0 ? hi - edge : hi - trim * (hi - lo);
			if (uv_pos[i] >= wlo && uv_pos[i] <= whi) {
				for (j = 0; j < nb; j++)
					out[k * nb + j] += uv[i * nb + j];
				cnt++;
			}
		}
		if (counts != NULL)
			counts[k] = cnt;
		for (j = 0; j < nb && cnt > 0; j++)
			out[k * nb + j] /= (double)cnt;
		cq_cnt_tmp[k < CQ_DUAL_MAXCELL ? k : CQ_DUAL_MAXCELL - 1] = cnt;
	}
	/* the verdict (workflow/dual_scan/cut.py::travel_verdict) */
	{
		int n = ncell < CQ_DUAL_MAXCELL ? ncell : CQ_DUAL_MAXCELL, zero = 0, few = 0;
		if (cq_cnt_tmp[0] == 0 || cq_cnt_tmp[n - 1] == 0)
			return "uv_pass_short";
		for (k = 0; k < n; k++) {
			if (cq_cnt_tmp[k] == 0) zero = 1;
			else if (cq_cnt_tmp[k] < min_readings) few = 1;
		}
		if (zero)
			return "uv_pass_stalled";
		if (few)
			return "uv_pass_too_fast";
	}
	/* the alignment gate (cut.py::_flatness, MAX_FLATNESS): the 400-500 nm
	 * UV signal's variance inside the cells against between them */
	{
		double f = cq_dual_flatness(nb, ncell, cells, lamp_pos, nuv, uv_pos, uv, trim);
		if (f == f && f > CQ_DUAL_MAX_FLATNESS)
			return "uv_pass_misaligned";
	}
	/* the same measure over the readings that are AVERAGED (the span less
	 * *edge*): the two passes lined up there too (header, CQ_DUAL_MAX_EDGE_FLATNESS) */
	if (edge >= 0.0) {
		double f = cq_dual_window_flatness(nb, ncell, cells, lamp_pos, nuv, uv_pos, uv, edge);
		if (f == f && f > CQ_DUAL_MAX_EDGE_FLATNESS)
			return "uv_pass_shifted";
	}
	return NULL;
}

static double cq_dual_flat_win(int nb, int ncell, const int (*cells)[2],
                               const double *lamp_pos, int nuv, const double *uv_pos,
                               const double *uv, double trim, double edge);

double cq_dual_flatness(int nb, int ncell, const int (*cells)[2],
                        const double *lamp_pos, int nuv, const double *uv_pos,
                        const double *uv, double trim) {
	return cq_dual_flat_win(nb, ncell, cells, lamp_pos, nuv, uv_pos, uv, trim, -1.0);
}

double cq_dual_window_flatness(int nb, int ncell, const int (*cells)[2],
                               const double *lamp_pos, int nuv, const double *uv_pos,
                               const double *uv, double edge) {
	return cq_dual_flat_win(nb, ncell, cells, lamp_pos, nuv, uv_pos, uv, 0.0, edge);
}

/* *edge* < 0: the window is the central part (trim at each end); else the
 * span less *edge* ruler steps at each end (the averaging window) */
static double cq_dual_flat_win(int nb, int ncell, const int (*cells)[2],
                               const double *lamp_pos, int nuv, const double *uv_pos,
                               const double *uv, double trim, double edge) {
	double within = 0.0, msum = 0.0, m2sum = 0.0, mu, var;
	int k, i, j, nm = 0;
	int b0 = nb > 13 ? 2 : 0, b1 = nb > 13 ? 13 : nb;
	for (k = 0; k < ncell; k++) {
		int s = cells[k][0], n = cells[k][1], cnt = 0;
		double a = lamp_pos[s], b = lamp_pos[s + n - 1];
		double lo = a < b ? a : b, hi = a < b ? b : a, w = hi - lo;
		double sum = 0.0, sq = 0.0;
		double wlo = edge >= 0.0 ? lo + edge : lo + trim * w;
		double whi = edge >= 0.0 ? hi - edge : hi - trim * w;
		for (i = 0; i < nuv; i++) {
			if (uv_pos[i] >= wlo && uv_pos[i] <= whi) {
				double sig = 0.0;
				for (j = b0; j < b1; j++)
					sig += uv[i * nb + j];
				sig /= (double)(b1 - b0);
				sum += sig;
				sq += sig * sig;
				cnt++;
			}
		}
		if (cnt < 2)
			continue;
		{
			double m = sum / (double)cnt;
			within += sq / (double)cnt - m * m;
			msum += m;
			m2sum += m * m;
			nm++;
		}
	}
	if (nm < 3)
		return (double)NAN;
	mu = msum / (double)nm;
	var = m2sum / (double)nm - mu * mu;
	if (var < 0.0)
		var = 0.0;
	if (!(fabs(mu) > 0.0 && sqrt(var) / fabs(mu) >= CQ_DUAL_MIN_ALIGN_SPREAD))
		return (double)NAN;
	return (within / (double)nm) / (var > 1e-30 ? var : 1e-30);
}

/* ---- lining the UV pass up with the lamp pass (second fix round) -------
 * chromiq_dualscan.h; the Python twin is cut.py::estimate_offset, step for
 * step: the lamp readings sorted by position, the prediction linearly
 * interpolated and held flat beyond the ends (numpy's interp), the shifts
 * -SPAN + k * STEP, the first smallest residual. */
typedef struct { double x, y; } cq_dual_xy;

static int cq_dual_xy_cmp(const void *a, const void *b) {
	double x = ((const cq_dual_xy *)a)->x, y = ((const cq_dual_xy *)b)->x;
	return x < y ? -1 : x > y ? 1 : 0;
}

static double cq_dual_interp(const cq_dual_xy *p, int n, double x) {
	int a = 0, b = n - 1;
	if (x <= p[0].x)
		return p[0].y;
	if (x >= p[n - 1].x)
		return p[n - 1].y;
	while (b - a > 1) {			/* p[a].x < x <= p[b].x */
		int c = (a + b) / 2;
		if (p[c].x < x) a = c;
		else b = c;
	}
	if (p[b].x == p[a].x)
		return p[b].y;
	return p[a].y + (p[b].y - p[a].y) * (x - p[a].x) / (p[b].x - p[a].x);
}

const char *cq_dual_align(int nlamp, const double *lamp_pos, const double *lamp_sig,
                          int nuv, const double *uv_pos, const double *uv_sig,
                          double lo, double hi, double *offset, double *rise) {
	cq_dual_xy *xy;
	int i, k, nk = (int)floor(2.0 * CQ_DUAL_ALIGN_SPAN / CQ_DUAL_ALIGN_STEP + 0.5) + 1;
	double *res, best = 0.0, bestd = 0.0, near = -1.0;
	int bestk = -1;
	if (offset != NULL) *offset = 0.0;
	if (rise != NULL) *rise = (double)NAN;
	if (nlamp < 2 || nuv < CQ_DUAL_ALIGN_MIN_READINGS || lamp_pos == NULL || lamp_sig == NULL
	 || uv_pos == NULL || uv_sig == NULL)
		return CQ_DUAL_NOT_LINED_UP;
	if ((xy = (cq_dual_xy *)malloc(sizeof(cq_dual_xy) * (size_t)nlamp)) == NULL)
		return "memory";
	if ((res = (double *)malloc(sizeof(double) * (size_t)nk)) == NULL) {
		free(xy);
		return "memory";
	}
	for (i = 0; i < nlamp; i++) {
		xy[i].x = lamp_pos[i];
		xy[i].y = lamp_sig[i];
	}
	qsort(xy, (size_t)nlamp, sizeof(cq_dual_xy), cq_dual_xy_cmp);
	for (k = 0; k < nk; k++) {
		double d = -CQ_DUAL_ALIGN_SPAN + k * CQ_DUAL_ALIGN_STEP;
		double pp = 0.0, pu = 0.0, us = 0.0, g, ss = 0.0;
		int n = 0;
		res[k] = -1.0;
		for (i = 0; i < nuv; i++) {
			double x = uv_pos[i] - d;
			if (x >= lo && x <= hi) {
				double pr = cq_dual_interp(xy, nlamp, x);
				pp += pr * pr;
				pu += pr * uv_sig[i];
				us += uv_sig[i];
				n++;
			}
		}
		if (n < CQ_DUAL_ALIGN_MIN_READINGS || !(pp > 0.0) || !(us != 0.0))
			continue;
		g = pu / pp;
		for (i = 0; i < nuv; i++) {
			double x = uv_pos[i] - d;
			if (x >= lo && x <= hi) {
				double e = uv_sig[i] - g * cq_dual_interp(xy, nlamp, x);
				ss += e * e;
			}
		}
		res[k] = sqrt(ss / (double)n) / (us / (double)n);
		if (bestk < 0 || res[k] < best) {
			best = res[k];
			bestk = k;
		}
	}
	if (bestk < 0) {
		free(xy);
		free(res);
		return CQ_DUAL_NOT_LINED_UP;
	}
	bestd = -CQ_DUAL_ALIGN_SPAN + bestk * CQ_DUAL_ALIGN_STEP;
	for (k = 0; k < nk; k++) {
		double d = -CQ_DUAL_ALIGN_SPAN + k * CQ_DUAL_ALIGN_STEP;
		if (res[k] >= 0.0 && fabs(d - bestd) >= 1.0 - 1e-9 && (near < 0.0 || res[k] < near))
			near = res[k];
	}
	free(xy);
	free(res);
	{
		/* a perfect fit (no noise) with a worse one a step away is clearly best */
		double r = near < 0.0 ? 1.0 : best > 0.0 ? near / best : near > 0.0 ? (double)INFINITY : 1.0;
		if (offset != NULL) *offset = bestd;
		if (rise != NULL) *rise = r;
		if (!(r >= CQ_DUAL_MIN_RISE))
			return CQ_DUAL_NOT_LINED_UP;	/* no clear patch edges: the caller keeps 4.3.54's window */
		if (fabs(bestd) > CQ_DUAL_MAX_OFFSET + 1e-9)
			return "uv_pass_shifted";
	}
	return NULL;
}

/* ---- the ruler positions of a hand dual strip (step 2) -------------------
 * One continuous ruler stream runs from the lamp pass's start ("ruler start")
 * to the UV pass's end ("ruler end"), one 2-bit quadrature sample per
 * integration clock. The ruler check's record keeps it as a change list
 * (cq_ruler.h: the first code, then per change the gap in samples and the
 * new code). The lamp pass's readings are the stream's first n1 * clk
 * samples, the UV pass's its last n2 * clk - 5 (the work-folder analysis of
 * 2026-11-17, process.py _uv_cut, which lined the recorded passes up within
 * about one ruler step). The position at each reading's centre is
 * interpolated between the count's changes inside its pass, held flat
 * beyond them (as ArgyllCMS's i1Pro 3 zebra code does). 1 = ok, 0 = the
 * stream is too short or the ruler hardly moved (fewer than 10 changes). */
static const int cq_dual_gray[4] = { 0, 1, 3, 2 };	/* code -> quadrature phase */

static int cq_dual_window(int first, int nch, const int *gaps, const unsigned char *codes,
                          long w0, long len, int n, int clk, double *out) {
	long at = 0;
	int k, prev = cq_dual_gray[first & 3], pos = 0, startpos = 0, nt = 0, i;
	static double tt[CQ_DUAL_MAXCHG + 1], pp[CQ_DUAL_MAXCHG + 1];	/* one helper, one reading at a time */
	for (k = 0; k < nch; k++) {
		int g = cq_dual_gray[codes[k] & 3], d = ((g - prev) % 4 + 4) % 4, np = pos;
		at += gaps[k];
		if (d == 1) np = pos + 1;
		else if (d == 3) np = pos - 1;
		prev = g;
		if (at <= w0) {
			pos = np;
			startpos = pos;
			continue;
		}
		if (at >= w0 + len)
			break;
		if (np != pos && nt < CQ_DUAL_MAXCHG) {
			if (nt == 0) {
				tt[0] = 0.0;
				pp[0] = (double)startpos;
				nt = 1;
			}
			tt[nt] = (double)(at - w0);
			pp[nt] = (double)np;
			nt++;
		}
		pos = np;
	}
	if (nt < 11)				/* fewer than 10 changes: the ruler did not move */
		return 0;
	for (i = 0; i < n; i++) {
		double x = (i + 0.5) * (double)clk;
		int j;
		if (x <= tt[0]) { out[i] = pp[0]; continue; }
		if (x >= tt[nt - 1]) { out[i] = pp[nt - 1]; continue; }
		for (j = 1; j < nt && tt[j] < x; j++)
			;
		out[i] = pp[j - 1] + (pp[j] - pp[j - 1]) * (x - tt[j - 1]) / (tt[j] - tt[j - 1]);
	}
	return 1;
}

int cq_dual_positions(int first, int nch, const int *gaps, const unsigned char *codes,
                      long total, int n1, int n2, int clk, double *lp, double *up) {
	long need1, need2;
	if (gaps == NULL || codes == NULL || nch <= 0 || n1 <= 0 || n2 <= 0 || clk <= 0)
		return 0;
	need1 = (long)n1 * clk;
	need2 = (long)n2 * clk - 5;
	if (need2 <= 0 || total < need1 + need2)
		return 0;
	return cq_dual_window(first, nch, gaps, codes, 0, need1, n1, clk, lp)
	    && cq_dual_window(first, nch, gaps, codes, total - need2, need2, n2, clk, up);
}

/* ---- the pairing check (safety review 2026-11-18, M1) ---------------------
 * workflow/dual_scan/pairing.py::check_pairing, line for line: the LED bands'
 * mean of (T / W) x L (predicted) and of U (observed) per patch; a patch takes
 * part when its prediction reaches (T / W) x LEVEL_FLOOR or its observation
 * twice that; fewer than MIN_USABLE such patches: not judged (accepted); the
 * median observed / predicted below MIN_LIGHT_RATIO: no UV light; the median
 * |ratio - 1| above MAX_RATIO_ERROR, or (with enough patches that differ
 * enough) the correlation below MIN_CORRELATION: the wrong strip. */
static int cq_dual_cmp(const void *a, const void *b) {
	double x = *(const double *)a, y = *(const double *)b;
	return x < y ? -1 : x > y ? 1 : 0;
}

static double cq_dual_median(double *v, int n) {	/* sorts v; numpy's median */
	qsort(v, (size_t)n, sizeof(double), cq_dual_cmp);
	if (n % 2)
		return v[n / 2];
	return (v[n / 2 - 1] + v[n / 2]) / 2.0;
}

/* the LED bands' mean of x[j] * f[j] (f NULL: of x[j]), as pairing._led */
static double cq_dual_led(const cq_dual_cal *c, const double *x, const double *f) {
	double s = 0.0;
	int j, k = 0;
	for (j = 0; j < c->nb; j++) {
		double wl = cq_dual_wl(c, j);
		if (wl >= CQ_DUAL_PAIR_LO - 1e-6 && wl <= CQ_DUAL_PAIR_HI + 1e-6) {
			double v = f != NULL ? x[j] * f[j] : x[j];
			s = k == 0 ? v : s + v;
			k++;
		}
	}
	return k > 0 ? s / (double)k : (double)NAN;
}

const char *cq_dual_pairing(const cq_dual_cal *c, int n, const double *L, const double *U,
                            cq_dual_pairing_ev *ev) {
	double tw[CQ_DUAL_NB], twf[CQ_DUAL_NB], floor_, *p = NULL, *o = NULL, *r = NULL;
	double med, err, corr = (double)NAN;
	int i, j, k = 0;
	const char *why = NULL;
	if (ev != NULL) {
		ev->correlation = ev->median_ratio_error = (double)NAN;
		ev->patches = n;
		ev->usable = 0;
		ev->checked = 0;
	}
	if ((why = cq_dual_check(c)) != NULL)
		return why;
	if (n <= 0 || L == NULL || U == NULL)
		return "uv_pass_count";
	for (j = 0; j < c->nb; j++) {
		tw[j] = c->T[j] / c->W[j];
		twf[j] = tw[j] * CQ_DUAL_PAIR_LEVEL_FLOOR;
	}
	floor_ = cq_dual_led(c, twf, NULL);
	p = (double *)malloc(sizeof(double) * (size_t)n);
	o = (double *)malloc(sizeof(double) * (size_t)n);
	r = (double *)malloc(sizeof(double) * (size_t)n);
	if (p == NULL || o == NULL || r == NULL) {
		why = "memory";
		goto done;
	}
	for (i = 0; i < n; i++) {
		double pr = cq_dual_led(c, L + i * c->nb, tw), ob = cq_dual_led(c, U + i * c->nb, NULL);
		if (!cq_dual_isfinite(pr) || !cq_dual_isfinite(ob)) {
			why = "bad_values";
			goto done;
		}
		if (pr >= floor_ || ob >= 2.0 * floor_) {
			p[k] = pr > 1e-12 ? pr : 1e-12;
			o[k] = ob;
			k++;
		}
	}
	if (ev != NULL)
		ev->usable = k;
	if (k < CQ_DUAL_PAIR_MIN_USABLE)
		goto done;					/* not judged: accepted, checked 0 */
	for (i = 0; i < k; i++)
		r[i] = o[i] / p[i];
	med = cq_dual_median(r, k);
	if (med < CQ_DUAL_PAIR_MIN_LIGHT_RATIO) {
		why = "uv_pass_no_uv_light";
		goto done;
	}
	for (i = 0; i < k; i++)
		r[i] = fabs(o[i] / p[i] - 1.0);
	err = cq_dual_median(r, k);
	if (k >= CQ_DUAL_PAIR_MIN_FOR_CORRELATION) {
		double mp = 0.0, mo = 0.0, vp = 0.0, vo = 0.0, cv = 0.0;
		for (i = 0; i < k; i++) {
			mp += p[i];
			mo += o[i];
		}
		mp /= (double)k;
		mo /= (double)k;
		for (i = 0; i < k; i++) {
			vp += (p[i] - mp) * (p[i] - mp);
			vo += (o[i] - mo) * (o[i] - mo);
			cv += (p[i] - mp) * (o[i] - mo);
		}
		if (sqrt(vp / (double)k) / mp >= CQ_DUAL_PAIR_MIN_SPREAD) {
			corr = cv / sqrt(vp * vo);
			if (corr > 1.0) corr = 1.0;
			if (corr < -1.0) corr = -1.0;
		}
	}
	if (ev != NULL) {
		ev->checked = 1;
		ev->median_ratio_error = err;
		ev->correlation = corr;
	}
	if (err > CQ_DUAL_PAIR_MAX_RATIO_ERROR || (corr == corr && corr < CQ_DUAL_PAIR_MIN_CORRELATION))
		why = "uv_pass_wrong_strip";
done:
	free(p);
	free(o);
	free(r);
	return why;
}
