/* CHROMIQ FILE: the strip SHIFT test (4.3.50, the patch finder study of
 * 2026-11-19). Pure arithmetic on numbers handed in: no instrument, no file,
 * no global. The helper calls it on a strip the instrument's patch finder
 * ACCEPTED, after the colour check passed and before the strip is kept;
 * tests call the same function (tests/strip_shift_test.c).
 *
 * WHY. ArgyllCMS's strip patch finder is told only how many patches a strip
 * has. The white run-up before the first patch is a flat stretch too, and
 * when the strip's label or a jolt at the start puts an edge in front of it,
 * the finder can take the run-up as patch 1: every reading then moves by one,
 * and one real patch is dropped further on (all of them, or only the first
 * few when a later boundary is missed and the readings fall back into step).
 * The same can happen at the end with the white after the last patch. Two
 * real cases on 2026-11-19: an i1Pro 3 strip refused by the colour check (a
 * whole strip moved) and an i1Pro 2 strip whose first three patches were
 * moved AND KEPT (colour check 88.2 against its limit of 95).
 *
 * THE TEST. For each end of the strip, in the order it would be filed, and
 * for the first k = 2 and k = 3 patches from that end:
 *   A_k  mean dE of each reading against its own expected colour,
 *   B_k  mean dE of each reading against the colour it would have if the
 *        readings had moved by one (paper at the end, then the patch before),
 *   D_k  mean dE between those two expected colours (how far apart the two
 *        explanations are),
 *   s_k = A_k - B_k  (positive: the readings fit "moved by one" better).
 * dE is CIE76 in L*a*b* D50 of Y-normalised readings, exactly the helper's
 * own colour check (xyzLabDE): ynorm = sum of expected Y / sum of read Y.
 * The strip is flagged when
 *   s_3 >= CQS_T3, or  s_2 >= CQS_T2 and s_2 >= CQS_F2 * D_2,
 * and, for either, D_k >= CQS_QMIN * M, M = the median dE between any two
 * expected colours of the strip: where the two explanations lie closer than
 * the strip's own colours do (a ramp, greys, a strip starting on white), a
 * shift cannot be told from a print that misses the design, and the test
 * says nothing rather than guess.
 *
 * Thresholds chosen from ~4,700 real strips that pass the colour check today
 * (~/Desktop/ChromIQ-work/2026-11-19_shift450, review_brief.txt): the worst
 * correct strip scores s_3 = 2.2, s_2 = 17.8 at a ratio of 0.26; the mildest
 * real misread s_3 = 11.4.
 *
 * ONE MOVED PATCH (k = 1, the commonest pattern in the study's simulation:
 * the run-up taken as patch 1 and the real patch 1 dropped, the rest in
 * step). s_1 alone cannot tell it from a light print of a colour the rough
 * expected values put far out of gamut (correct strips reach s_1 = 39), so it
 * is judged by the paper's own fingerprint instead: the end reading, AS READ
 * (not Y-normalised), is paper-like (L* >= CQS_P_L, chroma <= CQS_P_C) while
 * its expected colour is far from the paper (dE >= CQS_P_D). On the real
 * strips the brightest such reading of a correct strip is L* 69.7.
 *
 * AGPL-3.0 like the rest of ChromIQ's helper code (see License.txt). */
#ifndef CHROMIQ_SHIFT_H
#define CHROMIQ_SHIFT_H

#ifdef __cplusplus
extern "C" {
#endif

#define CQS_T3    10.0	/* s_3 at least this (dE)                          */
#define CQS_T2    20.0	/* s_2 at least this (dE) ...                      */
#define CQS_F2     0.5	/* ... and at least this share of D_2              */
#define CQS_QMIN   0.5	/* D_k at least this share of the strip's median dE */
#define CQS_NMIN   4	/* the shortest strip the test looks at            */
#define CQS_P_L   85.0	/* k = 1: the end reading's L* at least this ...   */
#define CQS_P_C   12.0	/* ... its chroma at most this ...                 */
#define CQS_P_D   50.0	/* ... and its expected colour this far from paper */

typedef struct {
	int    flagged;		/* 1: the strip looks moved by one patch           */
	int    end;			/* 0 = at the strip's first patch (as filed), 1 = at its last */
	int    k;			/* 1, 2 or 3: how many patches the finding rests on */
	double score;		/* the s_k that fired (or the largest s_k looked at);
						 * k = 1: the end reading's L* */
	double chroma;		/* k = 1: the end reading's chroma                 */
	double pd;			/* k = 1: dE of its expected colour from the paper */
	/* every figure, for the log and the tests: [end][k-2] */
	double s[2][2], d[2][2];
	double m;			/* the strip's median dE between expected colours  */
} cq_shift_result;

/* read[i], expd[i]: XYZ (0..100) of patch i in ROW order, as it would be
 * filed; paper: the expected XYZ of the chart's paper (its brightest expected
 * patch). Returns res->flagged. n < CQS_NMIN, no readable Y or a failed
 * allocation: not flagged. */
int cq_shift_test(const double (*read)[3], const double (*expd)[3], int n,
                  const double paper[3], cq_shift_result *res);

#ifdef __cplusplus
}
#endif
#endif /* CHROMIQ_SHIFT_H */
