/* CHROMIQ_EXT: which USB step failed (4.3.36, 2026-11-14).
 *
 * A tester's i1Pro 2 ended strips with "communication problem" and nothing
 * said which transfer had failed: ArgyllCMS's driver turns every USB error
 * into the one code I1PRO_COMS_FAIL (i1pro_imp.c icoms2i1pro_err). So the
 * helper WATCHES the instrument's three USB entry points (usb_control,
 * usb_read, usb_write in the icoms object) and remembers the transfers that
 * failed since the current reading began.
 *
 * READ-ONLY WITH RESPECT TO THE INSTRUMENT. Each wrapper calls the original
 * function with exactly the arguments it was given and returns exactly what
 * it returned; it only looks at the result afterwards. Nothing is sent,
 * retried, cancelled or reset by it, and no vendored ArgyllCMS file changes.
 * The fake-USB tests run the same lives with and without the watch and
 * compare the traces byte for byte (tests/test_usb_failure_detail.py).
 *
 * Only for the X-Rite i1Pro family (i1Pro, i1Pro 2: one driver) and the
 * i1Pro 3, whose transfers have known names; every other instrument is not
 * watched and its error event stays as it was.
 *
 * AGPL-3.0 like the rest of the helper (see ../instlib/License.txt). */
#ifndef CHROMIQ_USBWATCH_H
#define CHROMIQ_USBWATCH_H

#include <stddef.h>

struct _icoms;

/* Which driver's names apply. */
#define CQ_UW_I1PRO   1		/* i1pro_imp.c: the i1Pro and the i1Pro 2 */
#define CQ_UW_I1PRO3  3		/* i1pro3_imp.c */

/* What the failed transfer was. */
#define CQ_UW_CONTROL 0
#define CQ_UW_READ    1
#define CQ_UW_WRITE   2

/* The most failures one reading keeps (the first ones). */
#define CQ_UW_KEEP 4

typedef struct {
	int kind;			/* CQ_UW_CONTROL / _READ / _WRITE */
	int code;			/* control request, or endpoint */
	const char *step;	/* "measure_trigger", "measurement_read", ... */
	int icom;			/* the ICOM error the transfer returned */
	int asked;			/* bytes asked for */
	int done;			/* bytes transferred (-1: not reported) */
	int tout_ms;		/* the timeout the driver gave */
	int took_ms;		/* how long the call took */
	int at_ms;			/* ms since the reading began */
	int trigger_no;		/* measure triggers since the reading began */
} cq_uw_fail;

/* Wrap ic's three entry points for driver `family`. Once per instrument;
 * a different ic replaces the last one (which must be gone by then). */
void cq_usbwatch_install(struct _icoms *ic, int family);
/* Forget the instrument (before it is closed). */
void cq_usbwatch_forget(void);
/* A reading begins: forget what earlier readings recorded. */
void cq_usbwatch_begin(void);
/* The last light program the helper was told about (i1Pro 2 / 3 lights). */
void cq_usbwatch_light(const char *name);
/* The failures recorded since cq_usbwatch_begin, oldest first (at most
 * CQ_UW_KEEP); returns how many there were in all. */
int cq_usbwatch_failures(cq_uw_fail *out, int max, int *nout);
/* The JSON fields for the error event, starting with a comma, or "" when
 * nothing is watched: ,"usb_step":...,"usb":[...],"light":...,"light_ms":n */
void cq_usbwatch_json(char *dst, size_t dstlen);

#endif /* CHROMIQ_USBWATCH_H */
