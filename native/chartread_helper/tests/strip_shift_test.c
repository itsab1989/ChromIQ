/* The strip shift test (chromiq_shift.c) on strips read from stdin, for
 * tests/test_strip_shift_c.py, which computes the same with
 * workflow/strip_shift.py and compares every number. No instrument, no USB.
 *
 * Input, one strip after the other:
 *   STRIP <n> <other_best, -1: not known>
 *   <paper X Y Z>
 *   <read X Y Z> <expected X Y Z>      n lines, in row order
 * Output per strip:
 *   RESULT <i> <flagged> <end> <k> <score> <s[0][0]> <s[0][1]> <s[1][0]> <s[1][1]>
 *          <d[0][0]> <d[0][1]> <d[1][0]> <d[1][1]> <m> <chroma> <pd> <werror> <fit> <other> <guarded>
 * then "ALL DONE".
 * AGPL-3.0 - see ../../instlib/License.txt. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "chromiq_shift.h"

int main(void) {
	char word[32];
	int n, idx = 0;
	double other;
	while (scanf("%31s %d %lf", word, &n, &other) == 3) {
		double paper[3], (*rd)[3], (*ex)[3];
		cq_shift_result r;
		int i;
		if (strcmp(word, "STRIP") != 0 || n < 0 || n > 10000)
			return 2;
		if (scanf("%lf %lf %lf", &paper[0], &paper[1], &paper[2]) != 3)
			return 3;
		rd = malloc(sizeof(*rd) * (n + 1));
		ex = malloc(sizeof(*ex) * (n + 1));
		for (i = 0; i < n; i++)
			if (scanf("%lf %lf %lf %lf %lf %lf", &rd[i][0], &rd[i][1], &rd[i][2],
			          &ex[i][0], &ex[i][1], &ex[i][2]) != 6)
				return 4;
		cq_shift_test((const double (*)[3])rd, (const double (*)[3])ex, n, paper, other, &r);
		printf("RESULT %d %d %d %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %d\n",
		       idx++, r.flagged, r.end, r.k, r.score,
		       r.s[0][0], r.s[0][1], r.s[1][0], r.s[1][1],
		       r.d[0][0], r.d[0][1], r.d[1][0], r.d[1][1], r.m, r.chroma, r.pd, r.werror, r.fit, r.other, r.guarded);
		free(rd);
		free(ex);
	}
	printf("ALL DONE\n");
	return 0;
}
