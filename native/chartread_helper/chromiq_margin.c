/* CHROMIQ FILE: "margin tolerance" (Preferences > Beta, 2026-11-16).
 * Rules M ("margin at an end") and L ("no white leader"); see chromiq_margin.h.
 *
 * Every check refuses; only a reading that passes all of them is rescued:
 *   0. the ruler: a candidate counts only when the instrument travelled
 *      0.6 to 1.5 times the median patch length over it, IN THE STRIP'S
 *      DIRECTION, and it holds more than 3 readings (a stand-still, a lift, a
 *      sliver or a pass backwards is left out), and nothing the ruler left
 *      out may lie between two kept patches except a sliver of at most 3
 *      readings (the edge between two patches). Rows of fewer than 8 patches
 *      are not looked at (see cqm_decide);
 *  0a. the direction: the recording's ruler position may never fall back
 *      more than 3 steps against the strip's direction (its net travel), no
 *      segment, kept or forgiven, may move against it by more, and no segment
 *      may start or end on ground an earlier segment already covered. So the
 *      kept patches tile the travelled path in order, each once. A recording
 *      with any larger reversal stays refused, as ArgyllCMS decided
 *      (review 2026-11-16, BLOCKER-1: set down on patch 2, pulled back to the
 *      edge of patch 1, then swiped, counted patch 2 twice as a "patch 1");
 *   1. count: the kept candidates are the row's patch count, or one or two
 *      more;
 *   2. what is left out at either end is within 3 dE of the strip's paper
 *      white;
 *   3. neither the row's first nor its last expected patch is within 10 dE of
 *      paper white (a white end patch could be the margin itself);
 *   4. the kept patches match the expected row with a mean of at most 35 dE;
 *   5. no kept patch is paper white where the row expects a colour;
 *   6. that match is at most half the best alternative: every other row in
 *      both directions, and this row shifted by one or two patches either
 *      way, in both directions;
 *   7. each half of the row on its own is at most half of itself shifted by
 *      one patch (a split or a merge in the middle shifts one half only);
 *   8. no kept candidate is flagged by the driver (inconsistent, saturated,
 *      too few readings), as ArgyllCMS would refuse such a patch too.
 * Rule M uses the segments between the leader and the trailer; rule L (the
 * recording began on the first patch) also the first segment, only when the
 * ruler says it covered a whole patch, and takes the trailer as paper white,
 * only when it is within 3 dE (the margin's own limit) of the lightest
 * segment the ruler left out: a jig or a board 4 to 6 dE away is not paper.
 * When both rules accept different patches, the reading is refused.
 *
 * AGPL-3.0 like the rest of ChromIQ's helper code (see License.txt). */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "chromiq_margin.h"

const char *cqm_version(void) {
	return "M+L 2 (2026-11-16)";
}

void cqm_xyz2lab(const double xyz[3], double lab[3]) {
	static const double wp[3] = { 96.42, 100.0, 82.49 };
	double f[3];
	int i;
	for (i = 0; i < 3; i++) {
		double v = xyz[i] / wp[i];
		f[i] = v > 0.008856 ? cbrt(v) : 7.787 * v + 16.0 / 116.0;
	}
	lab[0] = 116.0 * f[1] - 16.0;
	lab[1] = 500.0 * (f[0] - f[1]);
	lab[2] = 200.0 * (f[1] - f[2]);
}

static double de(const double *a, const double *b) {
	double d0 = a[0] - b[0], d1 = a[1] - b[1], d2 = a[2] - b[2];
	return sqrt(d0 * d0 + d1 * d1 + d2 * d2);
}

/* Expected Lab of row r, patch i, read in direction dr (1 = back to front). */
static const double *ref(const cqm_chart *ch, int r, int dr, int i) {
	int N = ch->npatch;
	return ch->lab + 3 * ((size_t)r * N + (dr ? N - 1 - i : i));
}

/* Mean dE of the candidates (kept Lab, k of them) against row r in direction
 * dr at offset o; -1 when fewer than N-3 patches overlap. */
static double fit(const double (*C)[3], int n, const cqm_chart *ch, int r,
                  int dr, int o) {
	int N = ch->npatch, i, cnt = 0;
	double s = 0.0;
	for (i = 0; i < N; i++) {
		int j = o + i;
		if (j < 0 || j >= n)
			continue;
		s += de(C[j], ref(ch, r, dr, i));
		cnt++;
	}
	if (cnt < N - 3 || cnt <= 0)
		return -1.0;
	return s / cnt;
}

/* The rule on the kept candidates idx[0..n-1]. 1 = accept, fills out. */
static int decide(const cqm_cands *c, const int *idx, int n, const double *paper,
                  const cqm_chart *ch, cqm_result *out, char *why, size_t wsz) {
	int N = ch->npatch, k = n - N, o, dr, r, i, bo = -1, bdr = 0, half;
	double C[CQM_MAXC][3], bf = 1e30, rival = 1e30;

	if (k < 0 || k > 2) {
		snprintf(why, wsz, "count %d for %d patches", n, N);
		return 0;
	}
	for (i = 0; i < n; i++)
		memcpy(C[i], c->lab[idx[i]], sizeof(C[i]));
	/* 2: the best placement whose left-out ends are paper white */
	for (o = 0; o <= k; o++) {
		int ok = 1;
		for (i = 0; i < n && ok; i++)
			if ((i < o || i >= o + N) && de(C[i], paper) > CQM_T_PAPER)
				ok = 0;
		if (!ok)
			continue;
		for (dr = 0; dr < 2; dr++) {
			double f = fit((const double (*)[3])C, n, ch, ch->exp, dr, o);
			if (f >= 0.0 && f < bf) {
				bf = f;
				bo = o;
				bdr = dr;
			}
		}
	}
	if (bo < 0) {
		snprintf(why, wsz, "what would be left out is not paper white");
		return 0;
	}
	/* 3 */
	if (de(ref(ch, ch->exp, 0, 0), paper) < CQM_T_END
	 || de(ref(ch, ch->exp, 0, N - 1), paper) < CQM_T_END) {
		snprintf(why, wsz, "the row has an end patch near paper white");
		return 0;
	}
	/* 4 */
	if (bf > CQM_GOOD) {
		snprintf(why, wsz, "fit %.1f dE is above %.0f", bf, CQM_GOOD);
		return 0;
	}
	/* 5 */
	for (i = 0; i < N; i++)
		if (de(C[bo + i], paper) <= CQM_T_PAPER
		 && de(ref(ch, ch->exp, bdr, i), paper) >= CQM_T_END) {
			snprintf(why, wsz, "paper white where patch %d should be", i + 1);
			return 0;
		}
	/* 6: every alternative */
	for (r = 0; r < ch->rows; r++)
		for (dr = 0; dr < 2; dr++)
			for (o = -2; o <= k + 2; o++) {
				double f;
				if (r == ch->exp && dr == bdr && o == bo)
					continue;
				f = fit((const double (*)[3])C, n, ch, r, dr, o);
				if (f >= 0.0 && f < rival)
					rival = f;
			}
	if (rival < 1e29 && bf > CQM_RATIO * rival) {
		snprintf(why, wsz, "fit %.1f dE is not clearly better than %.1f", bf, rival);
		return 0;
	}
	/* 7: each half against itself shifted by one */
	for (half = 0; half < 2; half++) {
		int lo = half ? N / 2 : 0, hi = half ? N : N / 2, sh;
		double own = 0.0;
		if (hi - lo < 1)
			continue;
		for (i = lo; i < hi; i++)
			own += de(ref(ch, ch->exp, bdr, i), C[bo + i]);
		own /= (hi - lo);
		for (sh = -1; sh <= 1; sh += 2) {
			int cnt = 0;
			double alt = 0.0;
			for (i = lo; i < hi; i++) {
				int j = bo + i + sh;
				if (j < 0 || j >= n)
					continue;
				alt += de(ref(ch, ch->exp, bdr, i), C[j]);
				cnt++;
			}
			if (cnt < hi - lo - 1 || cnt <= 0)
				continue;
			alt /= cnt;
			if (own > CQM_RATIO * alt) {
				snprintf(why, wsz, "patches %d to %d are not clearly in place",
				         lo + 1, hi);
				return 0;
			}
		}
	}
	/* 8 */
	for (i = 0; i < N; i++)
		if (c->flags[idx[bo + i]] != 0) {
			snprintf(why, wsz, "patch %d is flagged by the driver (%d)", i + 1,
			         c->flags[idx[bo + i]]);
			return 0;
		}
	for (i = 0; i < N; i++)
		out->sel[i] = idx[bo + i];
	out->left_start = bo;
	out->left_end = k - bo;
	out->dir = bdr;
	out->fit = bf;
	out->rival = rival < 1e29 ? rival : -1.0;
	snprintf(why, wsz, "ok");
	return 1;
}

static int cmp_d(const void *a, const void *b) {
	double x = *(const double *)a, y = *(const double *)b;
	return x < y ? -1 : x > y;
}

/* 0: the candidates the ruler keeps, from first..last. ds = each segment's
 * travel in the strip's direction. Returns the count, or -1 when a left-out
 * candidate lies between two kept ones.
 *
 * WHY THE TRAVEL WINDOW (CQM_TRAV_LO..CQM_TRAV_HI) AND THE SLIVER RULE MUST
 * NOT BE LOOSENED. The colour rules (4 to 7) compare means over the row, so
 * on their own they accept, at 0.01 to 3 %, two kinds of wrong reading the
 * review built by hand (adv.py "lift" and "backforth"): a patch with no
 * segment at all (an instrument lifted over it, the neighbours making up the
 * count) and a patch counted twice with a full patch's travel each time.
 * Neither can happen here only because of the ruler: a patch the instrument
 * crossed has a segment that travelled about one patch (so no patch goes
 * missing while the count still fits, and nothing longer than 1.5 patches is
 * one patch), and a segment of more than 3 readings between two kept patches
 * refuses the reading (so a second pass cannot hide as a sliver). Rule 0a
 * makes the second pass impossible in the other direction. Widen any of
 * these and those readings come back. */
static int ruler_keep(const cqm_cands *c, const double *ds, int first, int last,
                      double med, int *idx, int *standing) {
	int i, n = 0, gap = 0;
	*standing = 0;
	for (i = first; i <= last; i++) {
		int ok = ds[i] >= CQM_TRAV_LO * med && ds[i] <= CQM_TRAV_HI * med
		      && c->no[i] > CQM_MIN_NO;
		if (ok) {
			if (gap && n > 0)
				return -1;
			idx[n++] = i;
		} else {
			(*standing)++;
			/* a sliver of 3 readings or fewer between two patches is the
			 * edge between them (ArgyllCMS's own grouping steps over it);
			 * anything longer inside the row refuses. A sliver is
			 * forgiven only because rule 0a has already proved that it did
			 * not move back: the ruler is what makes a repeated patch
			 * impossible, never the colour (see above). */
			if (n > 0 && c->no[i] > CQM_MIN_NO)
				gap = 1;
		}
	}
	return n;
}

/* 0a: the whole recording moves one way. d = the strip's direction (+1/-1).
 *
 * CQM_BACK_TOL, 3 steps: one step is the finest the ruler resolves (at most
 * about 1.1 mm on the i1Pro 2, workflow/ruler_check.py MM_PER_STEP_UPPER),
 * and a reader resting on a stripe edge can flicker by one. In the tester's
 * recordings of 2026-11-15, 157 of 159 strips fell back at most 2 steps
 * (154 not at all); the other two were real pulls back of 40 and 46 steps.
 * 3 is the smallest whole number above what correct movement showed, and a
 * quarter of a patch there (about 11 to 14 steps), so a fall-back within it
 * cannot carry the aperture back across a patch. */
static int ruler_one_way(const cqm_cands *c, const double *ds, int d,
                         char *why, size_t wsz) {
	int i;
	double hi = -1e30;
	if (!(c->back >= 0.0)) {
		snprintf(why, wsz, "the ruler's movement is not known");
		return 0;
	}
	if (c->back > CQM_BACK_TOL) {
		snprintf(why, wsz, "the ruler shows the instrument moved back %.0f steps",
		         c->back);
		return 0;
	}
	for (i = 0; i < c->n; i++) {
		double a = d * c->p0[i], b = a + ds[i];
		if (ds[i] < -CQM_BACK_TOL) {
			snprintf(why, wsz, "segment %d moved against the strip", i + 1);
			return 0;
		}
		if (a < hi - CQM_BACK_TOL || b < hi - CQM_BACK_TOL) {
			snprintf(why, wsz, "segment %d covers ground already read", i + 1);
			return 0;
		}
		if (a > hi)
			hi = a;
		if (b > hi)
			hi = b;
	}
	return 1;
}

int cqm_decide(const cqm_cands *c, const cqm_chart *ch, int why, cqm_result *out) {
	double med, inner[CQM_MAXC], ds[CQM_MAXC], maxL = -1e9;
	int n, i, idx[CQM_MAXC], m_ok = 0, l_ok = 0, nk, st, d;
	cqm_result rm, rl;

	memset(out, 0, sizeof(*out));
	memset(&rm, 0, sizeof(rm));
	memset(&rl, 0, sizeof(rl));
	/* rows of 8 patches or more only: the ruler check's own minimum for a
	 * question (MIN_PATCHES_FOR_QUESTION), and the shortest row a real chart
	 * of the reader review had was 9. On rows of 5 the review found 4 of 2,152
	 * "jumped" swipes (2 patches from the neighbour row) accepted: in a short
	 * row two wrong patches move the mean too little. */
	if (c == NULL || ch == NULL || ch->lab == NULL || ch->npatch < CQM_MIN_PATCH
	 || ch->rows < 1 || ch->exp < 0 || ch->exp >= ch->rows) {
		snprintf(out->why, sizeof(out->why), "no chart, or a row of fewer than %d patches",
		         CQM_MIN_PATCH);
		return 0;
	}
	if (why != CQM_WHY_NOTENOUGH && why != CQM_WHY_TOOMANY && why != CQM_WHY_LEADTRAIL) {
		snprintf(out->why, sizeof(out->why), "not a refusal these rules look at");
		return 0;
	}
	n = c->n;
	if (n < 3 || n > CQM_MAXC || n > 2 * ch->npatch + 8) {
		snprintf(out->why, sizeof(out->why), "%d segments", n);
		return 0;
	}
	d = c->net > 0.0 ? 1 : c->net < 0.0 ? -1 : 0;
	if (d == 0) {
		snprintf(out->why, sizeof(out->why), "no ruler travel");
		return 0;
	}
	for (i = 0; i < n; i++)
		ds[i] = d * c->steps[i];
	if (!ruler_one_way(c, ds, d, out->why, sizeof(out->why)))
		return 0;
	for (i = 0; i < n; i++)
		if (c->lab[i][0] > maxL)
			maxL = c->lab[i][0];
	for (i = 1; i < n - 1; i++)
		inner[i - 1] = ds[i];
	qsort(inner, n - 2, sizeof(double), cmp_d);
	med = inner[(n - 2) / 2];
	if (!(med > 0.0)) {
		snprintf(out->why, sizeof(out->why), "no ruler travel");
		return 0;
	}

	/* rule M: between the leader and the trailer; paper = the lighter end */
	{
		const double *paper = c->lab[0][0] >= c->lab[n - 1][0] ? c->lab[0] : c->lab[n - 1];
		if (paper[0] < maxL - CQM_PAPER_L)
			snprintf(rm.why, sizeof(rm.why), "neither end is paper white");
		else if ((nk = ruler_keep(c, ds, 1, n - 2, med, idx, &st)) < 0)
			snprintf(rm.why, sizeof(rm.why), "the ruler left out a segment inside the row");
		else if ((m_ok = decide(c, idx, nk, paper, ch, &rm, rm.why, sizeof(rm.why))))
			rm.standing = st;
	}
	/* rule L: the recording began on the first patch; paper = the trailer,
	 * which must be paper white within the 3 dE a margin is held to: of the
	 * lightest segment the ruler left out (a narrow paper margin before a
	 * jig or a board 4 to 6 dE away shows there, and then rule 5 would fail
	 * to see a margin counted as a patch), and, as for rule M, within 2 L*
	 * of the lightest segment of all (no patch is lighter than its paper) */
	{
		const double *paper = c->lab[n - 1];
		if (ds[0] < CQM_L_FULL * med)
			snprintf(rl.why, sizeof(rl.why), "the first segment is not a whole patch");
		else if (paper[0] < maxL - CQM_PAPER_L)
			snprintf(rl.why, sizeof(rl.why), "the trailer is not paper white");
		else if ((nk = ruler_keep(c, ds, 0, n - 2, med, idx, &st)) < 0)
			snprintf(rl.why, sizeof(rl.why), "the ruler left out a segment inside the row");
		else {
			int j, k, lo = n - 1;
			for (j = 0; j < n; j++) {
				for (k = 0; k < nk && idx[k] != j; k++)
					;
				if (k == nk && c->lab[j][0] > c->lab[lo][0])
					lo = j;
			}
			if (de(paper, c->lab[lo]) > CQM_T_PAPER)
				snprintf(rl.why, sizeof(rl.why), "the trailer is not paper white");
			else if ((l_ok = decide(c, idx, nk, paper, ch, &rl, rl.why, sizeof(rl.why))))
				rl.standing = st;
		}
	}

	if (m_ok && l_ok && memcmp(rm.sel, rl.sel, sizeof(int) * ch->npatch) != 0) {
		snprintf(out->why, sizeof(out->why), "rules M and L disagree");
		m_ok = l_ok = 0;
	} else if (m_ok) {
		*out = rm;
		out->rule = 'M';
		out->leader = 1;
		out->accept = 1;
		snprintf(out->why, sizeof(out->why), "ok");
	} else if (l_ok) {
		*out = rl;
		out->rule = 'L';
		out->leader = 0;
		out->accept = 1;
		snprintf(out->why, sizeof(out->why), "ok");
	} else
		snprintf(out->why, sizeof(out->why), "M: %s; L: %s", rm.why, rl.why);
	snprintf(out->why_m, sizeof(out->why_m), "%s", rm.why);
	snprintf(out->why_l, sizeof(out->why_l), "%s", rl.why);
	return out->accept;
}
