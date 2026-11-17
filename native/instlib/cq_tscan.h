/* CHROMIQ: the i1Pro 2 "table scan" (X-Rite i1iO 2, study, 2026-11-16).
 *
 * ChromIQ's own file, not part of ArgyllCMS; scripts/vendor_instlib.py never
 * writes it. The code is in cq_i1pro2_tscan.h, included once at the end of
 * i1pro_imp.c (the one recorded patch line), because it uses that file's
 * static trigger and read functions.
 *
 * What it is: the instrument's part of one ROW SCAN on the i1iO 2 table, as
 * X-Rite's i1Profiler 3.8.6 does it in four USB recordings of a user's table
 * (44 recorded passes, all the same form):
 *   lights off   0xD6 00000012, then the 18 OFF_SLOW bytes on bulk 0x03
 *                (0.62-1.77 s before the table's scan move m2)
 *   dark         0xD4 0000008b 00000000 00000005 0000  (5 x 5.004 ms, no lamp)
 *                data: 1340 bytes on 0x82
 *   lit          0xD4 0000008b 00000029 <N u32>  0100  (N x 5.004 ms, lamp
 *                pre-on 41 x 136 clocks = 200.7 ms, lamp flag, NO scan bit)
 *                data: N x 268 bytes on 0x82, one transfer
 *   status       0xC9 (8 bytes in)
 * The count N is fixed by the caller (from the planned move), never by the
 * instrument's button. Nothing else is sent: no EEPROM write (i1Profiler's
 * usage log is NOT copied), no ruler bits, no scan bit, no 0xD7.
 *
 * Nothing here runs unless ChromIQ's helper is started with
 * --i1io-table-scan and calls these functions; without that switch the
 * helper's wire bytes are those of 2026-11-15e (tests/test_i1io_table_scan.py).
 * AGPL-3.0 / GPLv2+ like the rest of the library. */

#ifndef CQ_TSCAN_H
#define CQ_TSCAN_H

#define CQ_TSCAN_INTCLOCKS   139	/* 5.004 ms at 36 us, as recorded (all 44 passes) */
#define CQ_TSCAN_LAMPCLOCKS  41		/* 200.7 ms lamp pre-on, as recorded */
#define CQ_TSCAN_DARK_N      5		/* dark readings before the lit pass, as recorded */
#define CQ_TSCAN_FLAGS_DARK  0x0000
#define CQ_TSCAN_FLAGS_LIT   0x0100	/* lamp, no scan bit, as recorded */
#define CQ_TSCAN_NMIN        10
/* The dark's read gives up after this (recorded: data 38-45 ms after the
 * trigger), so a failed dark cannot hold the lamp trigger back for long. */
#define CQ_TSCAN_DARK_TOUT   0.4
/* Recorded: 520 .. 1190 readings (2.6 .. 6.0 s). ArgyllCMS's own hand-held
 * strip scans may run up to MAXSCANTIME (30 s) of lamp-on time; 2000
 * readings = 10 s. */
#define CQ_TSCAN_NMAX        2000
/* Ready rules (the challenge of 2026-11-16, finding 8): the dark reading must
 * not be held back after the table's m2 has been sent, so the waits come
 * BEFORE it. Recorded spacing: lamp off -> next dark trigger >= 1.058 s;
 * lights-off write -> dark trigger >= 0.673 s (44 of 44 passes). */
#define CQ_TSCAN_LAMPOFF_MS  1070
#define CQ_TSCAN_LIGHTSOFF_MS 680
/* The white calibration must stay valid for the pass with room to spare. */
#define CQ_TSCAN_CAL_SPARE_S 120

/* What one fired pass gave. All times are msec_time() values. */
typedef struct {
	int nread;				/* readings asked for */
	int ngot;				/* lit readings received */
	int dark_ev, lit_ev, misc_ev;	/* i1pro_code of each step, 0 = ok */
	int dark_proc_ev;		/* the dark's own checks (inconsistent, too bright) */
	int dark_sent, lit_sent;	/* the 0xD4 went out (the trigger thread's own view) */
	unsigned int t_fire;	/* fire() was entered */
	unsigned int t_dark_trig, t_dark_data;
	unsigned int t_lit_trig, t_lit_data;
	unsigned int t_misc;
	unsigned int since_lamp_off_ms;		/* at fire */
	unsigned int since_lights_off_ms;	/* at fire, 0 = no lights-off this pass */
	int misc[5];			/* 0xC9: fwrev, unkn1, maxpve, unkn3, powmode */
	int maxraw;				/* highest raw sensor value in the lit pass */
	int saturated;			/* maxraw at or above the sensor's saturation level */
	unsigned char *raw_dark;	/* 5 x 268 bytes as received */
	int raw_dark_len;
	unsigned char *raw_lit;		/* ngot x 268 bytes as received */
	int raw_lit_len;
	int nwav;				/* bands per spectrum */
	double wl_short, wl_long;
	double *spec;			/* ngot x nwav calibrated reflectance (0..1), per reading */
	int npatch;				/* patches asked of ArgyllCMS's recogniser (0 = not asked) */
	int rec_ev;				/* its result, 0 = it found them */
	double *rec_spec;		/* npatch x nwav, when rec_ev == 0 */
} cq_tscan_rec;

/* Lights off, as recorded before every pass. Returns 0, or the ICOM error. */
int i1pro2_cq_tscan_lights_off(void *pp);
/* Can a pass of nread readings be fired now? 1 = yes; 0 = not yet, *wait_ms
 * says how long; -1 = never (why says it). */
int i1pro2_cq_tscan_ready(void *pp, int nread, int *wait_ms, char *why, int whylen);
/* Fire one pass: dark, lit, status. NO cancellation point and no wait: once
 * entered, the lit trigger is always attempted, even after a failed dark
 * (the table's pending scan move waits for the lamp). Then the readings are
 * processed. npatch > 0 also asks ArgyllCMS's recogniser for that many
 * patches (a cross-check only). Returns 0 when both readings arrived. */
int i1pro2_cq_tscan_fire(void *pp, int nread, int npatch, cq_tscan_rec *r);
void cq_tscan_rec_clear(cq_tscan_rec *r);

/* Tests only (fake USB): shorter ready waits, 0 = the real ones. */
extern int i1pro2_cq_tscan_lampoff_ms_for_test;
extern int i1pro2_cq_tscan_lightsoff_ms_for_test;
/* Tests only: stop after the wire part (a fake instrument has no EEPROM tables). */
extern int i1pro2_cq_tscan_noproc_for_test;

#endif /* CQ_TSCAN_H */
