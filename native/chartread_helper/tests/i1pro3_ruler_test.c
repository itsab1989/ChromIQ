/* i1pro3_ruler_test: the ruler check's i1Pro 3 hooks (2026-11-14) through the
 * REAL vendored driver entries, with no USB at all (the i1Pro 3 part sends
 * and reads nothing new: it copies what ArgyllCMS already read). Prints one
 * line per case; tests/test_ruler_scan_trace.py reads them.
 * AGPL-3.0 like the rest of the helper (see ../../instlib/License.txt). */
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
#include "cq_ruler.h"

static i1pro3 *make(void) {
	i1pro3 *p = (i1pro3 *)calloc(1, sizeof(i1pro3));
	p->log = new_a1log_d(NULL);
	p->dtype = instI1Pro3;
	p->inited = 1;
	if (add_i1pro3imp(p) != I1PRO3_OK)
		exit(2);
	((i1pro3imp *)p->m)->intclkp = 15.3e-6;
	((i1pro3imp *)p->m)->nraw = 128;
	((i1pro3imp *)p->m)->fwver = 105;
	return p;
}

static void show(const char *what, i1pro3 *p) {
	cq_ruler_rec r;
	if (i1pro3_cq_ruler_take(p, &r)) {
		printf("%s REC gen=%d ended=%d samples=%ld nch=%d first=%d readings=%d "
		       "clocks=%d used=%d ncut=%d domain=%d ntrace=%d\n", what, r.gen,
		       r.ended, r.samples, r.nch, r.first, r.readings, r.clocks,
		       r.argyll_used, r.ncut, r.cut_domain, r.ntrace);
		cq_ruler_rec_clear(&r);
	} else
		printf("%s REC none\n", what);
}

int main(void) {
	static const unsigned char cyc[4] = { 0, 2, 3, 1 };
	int n = 600 * 172, i;
	unsigned char *zeb = (unsigned char *)malloc(n);
	i1pro3_patch pat[18];
	double **mm = dmatrix(0, 99, 0, 127);
	double mx[128];
	i1pro3 *p = make();
	for (i = 0; i < n; i++)
		zeb[i] = cyc[(i / 300) & 3];
	for (i = 0; i < 100; i++) {
		int j;
		for (j = 0; j < 128; j++)
			mm[i][j] = 100.0 + i;
	}
	for (i = 0; i < 128; i++)
		mx[i] = 200.0;
	memset(pat, 0, sizeof(pat));
	for (i = 1; i < 17; i++) {
		pat[i].ss = 10 * i;
		pat[i].no = 5;
		pat[i].use = 1;
	}

	/* option off: every hook is a no-op */
	i1pro3_cq_ruler_zeb(p, zeb, n, 600, 172, 0.0026, n / 4);
	show("off", p);
	printf("off STATE %d\n", i1pro3_cq_ruler_state(p));

	/* on, but not armed (a patch read, a calibration) */
	printf("on OPTIONS %d\n", i1pro3_cq_ruler_options(p, 1));
	i1pro3_cq_ruler_zeb(p, zeb, n, 600, 172, 0.0026, n / 4);
	show("unarmed", p);

	/* an armed strip: the samples, ArgyllCMS's use, the cut and the trace */
	i1pro3_cq_ruler_arm(p, 1);
	i1pro3_cq_ruler_zeb(p, zeb, n, 600, 172, 0.0026, n / 4);
	i1pro3_cq_ruler_used(p, 1, 400);
	i1pro3_cq_ruler_trace(p, mm, 100, mx, 1);
	i1pro3_cq_ruler_cut(p, pat, 18, 1);
	i1pro3_cq_ruler_arm(p, 0);
	show("armed", p);

	/* one-shot: a second scan in the same read_strip is not recorded */
	i1pro3_cq_ruler_arm(p, 1);
	i1pro3_cq_ruler_zeb(p, zeb, n, 600, 172, 0.0026, n / 4);
	i1pro3_cq_ruler_zeb(p, zeb, 10, 1, 172, 0.0026, 3);
	show("oneshot", p);

	/* ArgyllCMS's own ruler read failed */
	i1pro3_cq_ruler_arm(p, 1);
	i1pro3_cq_ruler_failed(p, 0x100);
	show("failed", p);
	i1pro3_cq_ruler_close(p);
	printf("ALL DONE\n");
	return 0;
}
