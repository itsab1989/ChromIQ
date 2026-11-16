/* CHROMIQ FILE: "margin tolerance" (Preferences > Beta, 2026-11-16).
 *
 * The decision of rules M ("margin at an end") and L ("no white leader") for
 * an i1Pro 2 strip that ArgyllCMS's patch finder REFUSED ("Too many
 * patches", "Not enough patches", "Swipe didn't start and end on the media").
 * Pure arithmetic on numbers handed in: no instrument, no file, no global.
 * The helper calls it with the driver's candidate segments (every segment the
 * recogniser cut, in swipe order, each with its CIE Lab and its travel on the
 * ruler) and the chart's expected colours; tests call the same function.
 *
 * Specified and tested offline in the work notes of 2026-11-15 ("refused
 * readings", section C) and re-checked in real CIE dE on 2026-11-16.
 * A reading this accepts is handed to the helper's ordinary checks (row
 * correlation, back to front, slipped strip, ruler check, warnings) exactly
 * like one ArgyllCMS accepted.
 *
 * AGPL-3.0 like the rest of ChromIQ's helper code (see License.txt). */
#ifndef CHROMIQ_MARGIN_H
#define CHROMIQ_MARGIN_H

#ifdef __cplusplus
extern "C" {
#endif

#define CQM_MAXC 128		/* candidate segments considered */

/* The thresholds (CIE76 dE in CIE Lab D50, ruler steps, readings). */
#define CQM_T_PAPER   3.0	/* a left-out candidate is this close to paper white */
#define CQM_T_END    10.0	/* the row's first / last expected patch is at least this far from paper */
#define CQM_GOOD     35.0	/* the winning fit, mean dE per patch, at most */
#define CQM_RATIO     0.5	/* ... and at most this share of every alternative */
#define CQM_TRAV_LO   0.6	/* a candidate's ruler travel, as a share of the median */
#define CQM_TRAV_HI   1.5	/* (do not loosen: see chromiq_margin.c, rule 0) */
#define CQM_BACK_TOL  3.0	/* ruler steps the position may fall back (rule 0a) */
#define CQM_MIN_PATCH 8		/* the shortest row the rules look at (rule 0) */
#define CQM_MIN_NO    3		/* a candidate has MORE readings than this */
#define CQM_L_FULL    0.85	/* rule L: the first segment covers a whole patch */
#define CQM_PAPER_L   2.0	/* paper white is within this L* of the lightest segment */

/* Why ArgyllCMS refused (the only three readings the rules look at). */
#define CQM_WHY_NOTENOUGH 1	/* "Not enough patches" */
#define CQM_WHY_TOOMANY   2	/* "Too many patches" */
#define CQM_WHY_LEADTRAIL 3	/* "Swipe didn't start and end on the media" */

/* Candidate flags (from the driver; any of them refuses a reading using it). */
#define CQM_F_INCONS  1		/* the readings inside it disagree (ArgyllCMS's test) */
#define CQM_F_SAT     2		/* the sensor saturated */
#define CQM_F_SPARSE  4		/* too few readings after the trim */

typedef struct {
	int n;					/* candidates, in swipe order */
	int ss[CQM_MAXC];		/* first reading (untrimmed) */
	int no[CQM_MAXC];		/* readings (untrimmed) */
	double lab[CQM_MAXC][3];	/* CIE Lab D50 of the trimmed average */
	double steps[CQM_MAXC];	/* SIGNED ruler travel over the segment, steps
							 * (position at its last reading minus at its first) */
	int flags[CQM_MAXC];	/* CQM_F_* */
	double p0[CQM_MAXC];	/* ruler position at its first reading, steps */
	double net;				/* the whole recording's travel, last position minus
							 * first (its sign is the strip's direction) */
	double back;			/* the most the position fell back, at any point of
							 * the whole recording, against that direction
							 * (steps, >= 0; < 0 = not known: refused) */
} cqm_cands;

typedef struct {
	int rows;				/* rows (strips) of the chart */
	int npatch;				/* patches per row */
	const double *lab;		/* [rows][npatch][3] expected Lab, chart order */
	int exp;				/* the row being read */
} cqm_chart;

typedef struct {
	int accept;				/* 1 = rescued */
	char rule;				/* 'M' or 'L' (0 when refused before a rule ran) */
	int sel[CQM_MAXC];		/* [npatch] candidate indices, swipe order */
	int left_start;			/* white candidates left out before the first patch */
	int left_end;			/* white candidates left out after the last patch */
	int standing;			/* candidates left out by the ruler (stood still, too short / long) */
	int leader;				/* rule L: 0, the recording had no white leader */
	int dir;				/* 1 = the best fit reads the row back to front */
	double fit;				/* mean dE of the kept patches to the row */
	double rival;			/* the best alternative (other row, shift, direction) */
	char why[128];			/* a refusal's reason (plain words, English, for files) */
	char why_m[128];		/* rule M's own outcome */
	char why_l[128];		/* rule L's own outcome */
} cqm_result;

/* CIE XYZ (0..100, D50) to CIE Lab. */
void cqm_xyz2lab(const double xyz[3], double lab[3]);

/* Decide one refused reading. Returns out->accept. */
int cqm_decide(const cqm_cands *c, const cqm_chart *ch, int why, cqm_result *out);

/* The build of this rule set, for files (bumped with every threshold change). */
const char *cqm_version(void);

#ifdef __cplusplus
}
#endif
#endif /* CHROMIQ_MARGIN_H */
