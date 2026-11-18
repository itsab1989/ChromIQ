/* CHROMIQ: the X-Rite i1Pro 2 dual scan, the instrument part (2026-11-18,
 * step 2). ChromIQ's own file, not part of ArgyllCMS; included ONCE, at the
 * end of i1pro_imp.c (after the table scan), so that ArgyllCMS's own exported
 * driver functions do the work: i1pro_trigger_one_measure,
 * i1pro_readmeasurement, i1pro_dark_measure_1 / _2, i1pro_sens_to_absraw,
 * i1pro_sub_absraw, i1pro_absraw_to_abswav, i1pro_conv2XYZ and
 * i1pro2_getUVvolts. scripts/vendor_instlib.py never writes this file.
 * The API and what goes on the wire: cq_dual.h.
 *
 * Off (the helper never calls i1pro2_cq_dual_options with on = 1) every hook
 * the driver calls (lamp delay, ruler bits, readings, keep lamp, ruler
 * phase) returns at once and changes nothing.
 *
 * WHERE EACH NUMBER COMES FROM
 *   * kA / kD: the EEPROM image the driver already read at open (keys 0x2f77
 *     / 0x2f76, typed double in i1data_get_type), read-only, 18 values each.
 *   * the integration: the mode's own white calibration's s->inttime, for the
 *     tile's UV reading and for every reading of that mode (a scan: ArgyllCMS's
 *     minimum, i1Profiler's 139 clocks; a spot: what ArgyllCMS's adaptive white
 *     calibration chose). Calibration and reading at the SAME exposure, per
 *     light source (i1Profiler's own b1 file shows the cost of not doing so).
 *   * 10 dark + 5 UV-LED readings of the tile, then the volts: i1Profiler's
 *     dual calibration as recorded (work-folder analysis, F6).
 *   * the UV readings' pre-delay: a FIXED 41 lamp clocks (CQ_DUAL_UV_LAMPCLOCKS)
 *     on every UV-LED trigger, tile, spot and pass alike: what X-Rite
 *     i1Profiler sent on every one of the 76 UV-LED triggers recorded from two
 *     instruments (safety review 2026-11-18, M3). ArgyllCMS's own lamp time
 *     would give 102 clocks in scan mode and 51 in spot mode, neither recorded.
 *
 * ONLY RECORDED FORMS (safety review 2026-11-18, M2): every UV-LED trigger
 * goes through i1pro2_cq_dual_form_refused before anything is sent; a form
 * other than 0x0200 / 0x0209 with 41 lamp clocks is refused (an error, nothing
 * on the wire), so 0x0201 (a UV scan without "ruler end") cannot go out.
 *
 * AGPL-3.0 like the rest of ChromIQ's helper code (see License.txt). */

#include "cq_dual.h"

/* Test hook (the fake-USB harness only, like the table scan's): the wire
 * exactly as it is, the processing of the readings skipped (zeros), so the
 * requests can be tested without an instrument's EEPROM. */
int i1pro2_cq_dual_noproc_for_test = 0;

typedef struct {
	double kA[CQ_DUAL_BANDS], kD[CQ_DUAL_BANDS];
	int phase;				/* CQ_DUAL_PHASE_* of the next reading */
	int uv_lit;				/* a UV-LED trigger was sent and its read is not over */
	int uv_triggers;		/* UV-LED triggers since the last arm */
	/* the last UV reading, per reading (a pass) or one (a spot) */
	int un;
	double *U;
	int uclocks;
	/* the last lamp reading's patch spectra before the output conversion */
	int ln;
	double *L;
	int lclamp;
	int lamp_readings;		/* the lamp pass's readings (its ruler share) */
	int unread;				/* readings the last UV pass gave (also when refused) */
} cq_dual_state;

static cq_dual_state *cq_dual_s(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	if (p == NULL || p->dtype != instI1Pro2 || (m = (i1proimp *)p->m) == NULL || !m->cq_dual_on)
		return NULL;
	return (cq_dual_state *)m->cq_dual_rec;
}

/* Whether this instrument can do it, and its tables (read-only copies). */
int i1pro2_cq_dual_options(void *pp, int on, double *kA, double *kD) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	double *a, *d;
	unsigned int na = 0, nd = 0;
	int j;
	cq_dual_state *st;
	if (p == NULL || (m = (i1proimp *)p->m) == NULL || p->dtype != instI1Pro2 || !p->inited)
		return CQ_DUAL_NA_INSTRUMENT;
	if (!on) {
		m->cq_dual_on = 0;
		return CQ_DUAL_NA_OK;
	}
	if (!(m->capabilities2 & I1PRO_CAP2_UV_LED))
		return CQ_DUAL_NA_NO_UV_LED;
	if (m->data == NULL
	 || (a = m->data->get_doubles(m->data, &na, 0x2f77)) == NULL
	 || (d = m->data->get_doubles(m->data, &nd, 0x2f76)) == NULL
	 || na != CQ_DUAL_TABLE_N || nd != CQ_DUAL_TABLE_N)
		return CQ_DUAL_NA_NO_TABLES;
	if (m->highres)
		return CQ_DUAL_NA_HIGHRES;
	if (m->cq_dual_rec == NULL
	 && (m->cq_dual_rec = calloc(1, sizeof(cq_dual_state))) == NULL)
		return CQ_DUAL_NA_INSTRUMENT;
	st = (cq_dual_state *)m->cq_dual_rec;
	for (j = 0; j < CQ_DUAL_BANDS; j++) {
		st->kA[j] = j < CQ_DUAL_TABLE_N ? a[j] : 0.0;
		st->kD[j] = j < CQ_DUAL_TABLE_N ? d[j] : 0.0;
		if (kA != NULL) kA[j] = st->kA[j];
		if (kD != NULL) kD[j] = st->kD[j];
	}
	m->cq_dual_on = 1;
	/* a hand dual strip needs the ruler: the ruler check's own reader
	 * (cq_ruler.h), switched on for the session; it sends nothing unless a
	 * reading is armed. Without the sensor, spot readings still work. */
	(void)i1pro2_cq_ruler_options(pp, 1);
	return CQ_DUAL_NA_OK;
}

/* The phase of the NEXT reading (the helper, around one read call). OFF on
 * every way out: the UV LED is used only for a reading armed as UV, and
 * ArgyllCMS's own UV switch (m->uv_en) is never left on. */
void i1pro2_cq_dual_arm(void *pp, int phase) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	cq_dual_state *st = cq_dual_s(pp);
	if (st == NULL)
		return;
	m = (i1proimp *)p->m;
	if (phase != CQ_DUAL_PHASE_LAMP && phase != CQ_DUAL_PHASE_UV
	 && phase != CQ_DUAL_PHASE_SPOT)
		phase = CQ_DUAL_PHASE_OFF;
	st->phase = phase;
	if (phase != CQ_DUAL_PHASE_OFF)
		st->uv_triggers = 0;	/* counted per armed reading, kept for the take */
	m->uv_en = phase == CQ_DUAL_PHASE_UV;	/* ArgyllCMS's own UV-LED reading path */
	if (phase == CQ_DUAL_PHASE_LAMP) {
		free(st->L);
		st->L = NULL;
		st->ln = 0;
		st->lamp_readings = 0;
	}
	if (phase == CQ_DUAL_PHASE_UV || phase == CQ_DUAL_PHASE_LAMP) {
		free(st->U);
		st->U = NULL;
		st->un = 0;
		st->unread = 0;
	}
	if (phase == CQ_DUAL_PHASE_OFF)
		st->uv_lit = 0;
}

int i1pro2_cq_dual_phase(void *pp) {
	cq_dual_state *st = cq_dual_s(pp);
	return st == NULL ? CQ_DUAL_PHASE_OFF : st->phase;
}

int i1pro2_cq_dual_uv_lit(void *pp) {
	cq_dual_state *st = cq_dual_s(pp);
	return st != NULL && st->uv_lit;
}

/* ---- the driver's hooks (i1pro_imp.c, CHROMIQ PATCH: dual scan) ---- */

/* i1pro_trigger_one_measure, where ArgyllCMS gives a reading without the
 * lamp 0 lamp clocks: the recorded 41 for a UV-LED reading of the dual scan
 * (i1Profiler's on every recorded UV-LED trigger), 0 for anything else and
 * whenever the dual scan is off. Never touches s->lamptime. */
int i1pro2_cq_dual_lamp_delay(void *pp, int mmodif) {
	i1pro *p = (i1pro *)pp;
	cq_dual_state *st = cq_dual_s(pp);
	i1proimp *m;
	if (st == NULL || (mmodif != i1p2_UV && mmodif != i1p2_cq_UV_cal))
		return 0;
	m = (i1proimp *)p->m;
	if (!m->ms[m->mmode].reflective)
		return 0;
	return CQ_DUAL_UV_LAMPCLOCKS;
}

/* i1pro_trigger_one_measure, after the flags and before anything is sent:
 * 1 = REFUSE this trigger (the caller returns an error, nothing goes on the
 * wire). With the dual scan on, a UV-LED trigger must be one of the recorded
 * forms: 0x0200 (the tile, a spot) or 0x0209 (the hand UV pass: scan + ruler
 * end), each with the recorded 41 lamp clocks. Counts the UV triggers that
 * go out. Off: 0, always (ArgyllCMS's own UV mode is untouched). */
int i1pro2_cq_dual_form_refused(void *pp, int flags2, int lampclocks) {
	cq_dual_state *st = cq_dual_s(pp);
	if (st == NULL || (flags2 & (I1PRO2_MMF_UV_LED | I1PRO2_MMF_LAMP)) != I1PRO2_MMF_UV_LED)
		return 0;
	if ((flags2 != CQ_DUAL_FORM_UV_TILE && flags2 != CQ_DUAL_FORM_UV_PASS)
	 || lampclocks != CQ_DUAL_UV_LAMPCLOCKS)
		return 1;
	st->uv_triggers++;
	st->uv_lit = 1;
	return 0;
}

/* The UV pass of a hand strip may be asked for (and its trigger carry "ruler
 * end"): the lamp pass counted readings in a ruler stream that still runs and
 * the ruler is in use. The helper asks for the UV pass only then; otherwise
 * M1 / M2 end for the session and M0 goes on. */
static int cq_dual_uv_ready(i1pro *p, cq_dual_state *st) {
	i1proimp *m = (i1proimp *)p->m;
	i1pro_state *s = &m->ms[m->mmode];
	return st != NULL && st->lamp_readings > 0 && m->cq_ruler_on && !m->cq_ruler_given_up
	    && m->cq_ruler_th != NULL && s->scan && s->reflective;
}

int i1pro2_cq_dual_uv_pass_ready(void *pp) {
	cq_dual_state *st = cq_dual_s(pp);
	return st != NULL && cq_dual_uv_ready((i1pro *)pp, st);
}

/* The ruler flags of the dual scan's two passes: the lamp pass "ruler
 * start" (0x0105 on the wire), the UV pass "ruler end" (0x0209). Only for an
 * armed hand strip, only while the ruler is in use, and the reader started
 * at the lamp pass keeps the stream running into the UV pass. */
int i1pro2_cq_dual_ruler_bits(void *pp, int mmodif) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	i1pro_state *s;
	cq_dual_state *st = cq_dual_s(pp);
	if (st == NULL)
		return 0;
	m = (i1proimp *)p->m;
	s = &m->ms[m->mmode];
	if (!m->cq_ruler_on || m->cq_ruler_given_up || !s->scan || !s->reflective)
		return 0;
	if (m->cq_ruler_inscan)
		return 0;		/* the ruler check (Beta) armed this scan itself: never both */
	if (st->phase == CQ_DUAL_PHASE_LAMP && mmodif == i1p_norm && m->cq_ruler_th == NULL) {
		m->cq_ruler_inscan = 1;
		return I1PRO2_MMF_RULER_START;
	}
	if (st->phase == CQ_DUAL_PHASE_UV && mmodif == i1p2_UV && cq_dual_uv_ready(p, st)) {
		m->cq_ruler_inscan = 1;
		return I1PRO2_MMF_RULER_END;
	}
	return 0;
}

/* The ruler code: 1 = the lamp pass (its stream runs on), 3 = the UV pass
 * (no new reader: the lamp pass's carries on). */
int i1pro2_cq_dual_ruler_phase(void *pp) {
	cq_dual_state *st = cq_dual_s(pp);
	return st == NULL ? CQ_DUAL_PHASE_OFF : st->phase;
}

int i1pro2_cq_dual_lamp_count(void *pp) {
	cq_dual_state *st = cq_dual_s(pp);
	return st == NULL ? 0 : st->lamp_readings;
}

void i1pro2_cq_dual_lamp_readings(void *pp, int nreadings) {
	cq_dual_state *st = cq_dual_s(pp);
	if (st != NULL)
		st->lamp_readings = nreadings;
}

/* i1pro_read_patches_2: a UV pass keeps EVERY reading (lamp-white units)
 * and is not put through ArgyllCMS's patch recogniser (the UV pass carries
 * almost no colour); the patch values it returns are placeholders the helper
 * never files. Returns 1 when it took the readings. */
int i1pro2_cq_dual_readings(void *pp, double **multimes, int nmeas, double **absraw,
                            int npatch) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	i1pro_state *s;
	cq_dual_state *st = cq_dual_s(pp);
	double **wav;
	int i, j, n;
	if (st == NULL || st->phase != CQ_DUAL_PHASE_UV)
		return 0;
	m = (i1proimp *)p->m;
	s = &m->ms[m->mmode];
	st->uv_lit = 0;				/* the reading is over */
	st->unread = nmeas;
	/* a pass longer than CQ_DUAL_MAX_UV_READINGS (about 20 s) is refused
	 * whole, never half-used: its readings and the ruler's positions (the
	 * stream's LAST n x clocks samples) would no longer belong together */
	n = nmeas <= CQ_DUAL_MAX_UV_READINGS ? nmeas : 0;
	free(st->U);
	st->U = NULL;
	st->un = 0;
	if (n > 0 && i1pro2_cq_dual_noproc_for_test
	 && (st->U = (double *)calloc((size_t)(CQ_DUAL_BANDS * n), sizeof(double))) != NULL) {
		st->un = n;
		st->uclocks = m->c_intclocks;
	} else if (n > 0 && (st->U = (double *)malloc(sizeof(double) * CQ_DUAL_BANDS * n)) != NULL) {
		wav = dmatrix(0, n - 1, 0, m->nwav[0] - 1);
		i1pro_absraw_to_abswav(p, 0, s->reflective, n, wav, multimes);
		for (i = 0; i < n; i++)
			for (j = 0; j < CQ_DUAL_BANDS && j < m->nwav[0]; j++)
				st->U[i * CQ_DUAL_BANDS + j] = wav[i][j] * s->cal_factor[0][j];
		free_dmatrix(wav, 0, n - 1, 0, m->nwav[0] - 1);
		st->un = n;
		st->uclocks = m->c_intclocks;
	}
	for (i = 0; i < npatch && !i1pro2_cq_dual_noproc_for_test; i++)	/* placeholders: the first reading */
		for (j = -1; j < m->nraw; j++)
			absraw[i][j] = nmeas > 0 ? multimes[0][j] : 0.0;
	return 1;
}

/* i1pro_imp_measure, before the output conversion: the lamp reading's
 * patch spectra (L of the formula) and the clamp, for a dual reading. */
void i1pro2_cq_dual_keep_lamp(void *pp, double **specrd, int nvals, int clamp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	cq_dual_state *st = cq_dual_s(pp);
	int i, j;
	if (st == NULL || (st->phase != CQ_DUAL_PHASE_LAMP && st->phase != CQ_DUAL_PHASE_SPOT)
	 || nvals <= 0)
		return;
	m = (i1proimp *)p->m;
	if (m->highres)
		return;					/* refused at options; never kept */
	free(st->L);
	if ((st->L = (double *)malloc(sizeof(double) * CQ_DUAL_BANDS * nvals)) == NULL) {
		st->ln = 0;
		return;
	}
	for (i = 0; i < nvals; i++)
		for (j = 0; j < CQ_DUAL_BANDS; j++)
			st->L[i * CQ_DUAL_BANDS + j] = j < m->nwav[0] ? specrd[i][j] : 0.0;
	st->ln = nvals;
	st->lclamp = clamp;
}

/* ---- what the helper calls ---- */

static void cq_dual_volts(i1pro *p, int *before, int *after) {
	if (i1pro2_getUVvolts(p, before, after) != I1PRO_OK) {
		*before = -1;
		*after = -1;
	}
}

/* n dark readings then n UV-LED readings at the current mode's integration,
 * averaged into U (lamp-white units). *mmodif* i1p2_cq_UV_cal (no scan). */
static i1pro_code cq_dual_uv_readings(i1pro *p, int ndark, int nuv, double *U, int *clocks) {
	i1proimp *m = (i1proimp *)p->m;
	i1pro_state *s = &m->ms[m->mmode];
	cq_dual_state *st = (cq_dual_state *)m->cq_dual_rec;
	double inttime = s->inttime, darkthresh;
	double *dark = NULL, **mm = NULL, **avg = NULL, **wav = NULL;
	unsigned char *buf = NULL;
	unsigned int bsize;
	int n = ndark > nuv ? ndark : nuv, j, k, got = 0;
	i1pro_code ev;

	bsize = m->nsen * 2 * n;
	if ((buf = (unsigned char *)malloc(bsize > 0 ? bsize : 1)) == NULL)
		return I1PRO_INT_MALLOC;
	dark = dvectorz(-1, m->nraw - 1);
	if ((ev = i1pro_dark_measure_1(p, ndark, &inttime, 0, buf, m->nsen * 2 * ndark)) == I1PRO_OK
	 && !i1pro2_cq_dual_noproc_for_test)
		ev = i1pro_dark_measure_2(p, dark, ndark, inttime, 0, buf, m->nsen * 2 * ndark);
	if (ev == I1PRO_OK) {
		ev = i1pro_trigger_one_measure(p, nuv, &inttime, 0, i1p2_cq_UV_cal);
		if (ev == I1PRO_OK)
			ev = i1pro_readmeasurement(p, nuv, 0, buf, m->nsen * 2 * nuv, &got, i1p2_cq_UV_cal);
		st->uv_lit = 0;			/* a non-scan reading of nuv readings: over */
	}
	if (ev == I1PRO_OK && got < 1)
		ev = I1PRO_RD_SHORTMEAS;
	if (ev == I1PRO_OK && i1pro2_cq_dual_noproc_for_test) {
		for (j = 0; j < CQ_DUAL_BANDS; j++)
			U[j] = 0.0;
		if (clocks != NULL)
			*clocks = m->c_intclocks;
		free_dvector(dark, -1, m->nraw - 1);
		free(buf);
		return ev;
	}
	if (ev == I1PRO_OK) {
		mm = dmatrix(0, got - 1, -1, m->nraw - 1);
		darkthresh = m->sens_dark + inttime * 900.0;
		ev = i1pro_sens_to_absraw(p, mm, buf, got, inttime, 0, &darkthresh);
	}
	if (ev == I1PRO_OK) {
		i1pro_sub_absraw(p, got, inttime, 0, mm, dark);
		avg = dmatrix(0, 0, -1, m->nraw - 1);
		wav = dmatrix(0, 0, 0, m->nwav[0] - 1);
		for (j = -1; j < m->nraw; j++) {
			avg[0][j] = 0.0;
			for (k = 0; k < got; k++)
				avg[0][j] += mm[k][j];
			avg[0][j] /= (double)got;
		}
		i1pro_absraw_to_abswav(p, 0, s->reflective, 1, wav, avg);
		for (j = 0; j < CQ_DUAL_BANDS; j++)
			U[j] = j < m->nwav[0] ? wav[0][j] * s->cal_factor[0][j] : 0.0;
		if (clocks != NULL)
			*clocks = m->c_intclocks;
	}
	if (mm != NULL) free_dmatrix(mm, 0, got - 1, -1, m->nraw - 1);
	if (avg != NULL) free_dmatrix(avg, 0, 0, -1, m->nraw - 1);
	if (wav != NULL) free_dmatrix(wav, 0, 0, 0, m->nwav[0] - 1);
	free_dvector(dark, -1, m->nraw - 1);
	free(buf);
	return ev;
}

/* (a) THE DUAL CALIBRATION, right after ArgyllCMS's own reflective white
 * calibration of the current mode (its s->inttime is the reading's): 10 dark
 * + 5 UV-LED readings of the tile at that integration, then the volts. W is
 * the white calibration's own reading of the tile, both in lamp-white units. */
int i1pro2_cq_dual_tile(void *pp, cq_dual_tile *out) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	i1pro_state *s;
	cq_dual_state *st = cq_dual_s(pp);
	double **ww, **wa;
	int j, j2;
	i1pro_code ev;
	if (out == NULL)
		return I1PRO_INT_ASSERT;
	memset(out, 0, sizeof(*out));
	out->volts_before = out->volts_after = -1;
	if (st == NULL)
		return I1PRO_INT_ASSERT;
	m = (i1proimp *)p->m;
	s = &m->ms[m->mmode];
	if (!s->reflective || !s->cal_valid || m->highres)
		return I1PRO_RD_NEEDS_CAL;
	st->phase = CQ_DUAL_PHASE_OFF;
	m->uv_en = 0;
	ev = cq_dual_uv_readings(p, CQ_DUAL_TILE_DARK, CQ_DUAL_TILE_UV, out->T, &out->uv_clocks);
	if (ev != I1PRO_OK)
		return ev;
	cq_dual_volts(p, &out->volts_before, &out->volts_after);
	if (i1pro2_cq_dual_noproc_for_test) {
		out->lamp_clocks = (int)floor(s->inttime / m->intclkp + 0.5);
		out->mode_scan = s->scan;
		out->ok = 1;
		return I1PRO_OK;
	}
	/* W: the white calibration's tile reading, as the lamp pass sees it */
	ww = dmatrix(0, 0, -1, m->nraw - 1);
	wa = dmatrix(0, 0, 0, m->nwav[0] - 1);
	for (j2 = -1; j2 < m->nraw; j2++)
		ww[0][j2] = s->white_data[j2];
	i1pro_absraw_to_abswav(p, 0, s->reflective, 1, wa, ww);
	for (j = 0; j < CQ_DUAL_BANDS; j++) {
		out->W[j] = j < m->nwav[0] ? wa[0][j] * s->cal_factor[0][j] : 0.0;
		out->E[j] = j < m->nwav[0] && s->cal_factor[0][j] != 0.0
		          ? m->emis_coef[0][j] / s->cal_factor[0][j] : 0.0;
	}
	free_dmatrix(ww, 0, 0, -1, m->nraw - 1);
	free_dmatrix(wa, 0, 0, 0, m->nwav[0] - 1);
	out->lamp_clocks = (int)floor(s->inttime / m->intclkp + 0.5);
	out->mode_scan = s->scan;
	out->ok = 1;
	return I1PRO_OK;
}

/* (b) THE UV HALF OF A DUAL SPOT, right after the lamp spot reading of the
 * same patch (the same press): dark + UV readings at the spot mode's
 * integration, as many as ArgyllCMS's own spot reading takes, then the
 * volts (the table recording: dark + lamp, then dark + UV, then 0xD8). */
int i1pro2_cq_dual_spot_uv(void *pp, cq_dual_uv *out) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	i1pro_state *s;
	cq_dual_state *st = cq_dual_s(pp);
	int n;
	i1pro_code ev;
	if (out == NULL)
		return I1PRO_INT_ASSERT;
	memset(out, 0, sizeof(*out));
	out->volts_before = out->volts_after = -1;
	if (st == NULL)
		return I1PRO_INT_ASSERT;
	m = (i1proimp *)p->m;
	s = &m->ms[m->mmode];
	if (!s->reflective || s->scan || !s->cal_valid || m->highres)
		return I1PRO_RD_NEEDS_CAL;
	m->uv_en = 0;
	n = i1pro_comp_nummeas(p, s->wreadtime, s->inttime);
	if (n < 1)
		n = 1;
	if ((out->U = (double *)malloc(sizeof(double) * CQ_DUAL_BANDS)) == NULL)
		return I1PRO_INT_MALLOC;
	st->uv_triggers = 0;
	ev = cq_dual_uv_readings(p, n, n, out->U, &out->clocks);
	out->uv_triggers = st->uv_triggers;
	if (ev != I1PRO_OK) {
		free(out->U);
		out->U = NULL;
		return ev;
	}
	cq_dual_volts(p, &out->volts_before, &out->volts_after);
	out->n = 1;
	return I1PRO_OK;
}

/* (c) the last UV pass, per reading (ownership moves to the caller). */
int i1pro2_cq_dual_take_uv(void *pp, cq_dual_uv *out) {
	i1pro *p = (i1pro *)pp;
	cq_dual_state *st = cq_dual_s(pp);
	if (out == NULL)
		return 0;
	memset(out, 0, sizeof(*out));
	out->volts_before = out->volts_after = -1;
	if (st != NULL) {
		out->nread = st->unread;
		st->unread = 0;
	}
	if (st == NULL || st->U == NULL || st->un <= 0)
		return 0;
	out->n = st->un;
	out->U = st->U;
	out->clocks = st->uclocks;
	out->uv_triggers = st->uv_triggers;
	st->U = NULL;
	st->un = 0;
	cq_dual_volts(p, &out->volts_before, &out->volts_after);	/* as recorded: after each UV pass */
	return 1;
}

int i1pro2_cq_dual_take_lamp(void *pp, cq_dual_lamp *out) {
	cq_dual_state *st = cq_dual_s(pp);
	if (out == NULL)
		return 0;
	memset(out, 0, sizeof(*out));
	if (st == NULL || st->L == NULL || st->ln <= 0)
		return 0;
	out->n = st->ln;
	out->L = st->L;
	out->clamp = st->lclamp;
	st->L = NULL;
	st->ln = 0;
	return 1;
}

/* M1 / M2 through the SAME output conversion as M0 (ArgyllCMS's
 * i1pro_conv2XYZ: XRGA when asked for, the observer, the clamp). */
int i1pro2_cq_dual_conv(void *pp, void *vals, int n, const double *spec, int clamp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	double **sp;
	int i, j;
	i1pro_code ev;
	if (cq_dual_s(pp) == NULL || vals == NULL || spec == NULL || n <= 0)
		return I1PRO_INT_ASSERT;
	m = (i1proimp *)p->m;
	sp = dmatrix(0, n - 1, 0, m->nwav[0] - 1);
	for (i = 0; i < n; i++)
		for (j = 0; j < m->nwav[0]; j++)
			sp[i][j] = j < CQ_DUAL_BANDS ? spec[i * CQ_DUAL_BANDS + j] : 0.0;
	ev = i1pro_conv2XYZ(p, (ipatch *)vals, n, sp, (instClamping)clamp);
	free_dmatrix(sp, 0, n - 1, 0, m->nwav[0] - 1);
	return ev;
}

/* ==== (d) THE i1iO 2 TABLE (2026-11-18, "table dual"; the volunteer's
 * recordings of i1Profiler 3.8.6 doing a dual scan on his table) ====
 *
 * Only ChromIQ's helper in its table-scan mode WITH --i1io-table-dual, and
 * the patch-by-patch reading WITH --dual-table, ever call these. What goes on
 * the wire is the recorded dual row, pass by pass (cq_tscan.h has the single
 * row):
 *   lamp pass   0xD4 0000008b 00000029 <N> 0100   (lit FIRST, N x 5.004 ms)
 *               0xC9 (8 bytes in, as after every recorded lamp pass)
 *               0xD4 0000008b 00000000 00000005 0000   (5 dark AFTER the pass)
 *   UV pass     0xD4 0000008b 00000029 <N> 0200   (the UV LED, through the
 *               dual scan's form gate: 0x0200 with the fixed 41 lamp clocks)
 *               0xD4 0000008b 00000000 00000005 0000   (5 dark AFTER)
 *               0xD8 (the UV LED's volts, read only)
 * and on the table's tile, right after ArgyllCMS's own strip white:
 *   10 dark + 5 UV-LED readings at the strip integration, then 0xD8
 * (i1pro2_cq_dual_tile, the hand dual scan's own, unchanged). Nothing else:
 * no EEPROM write, no lights program but the table scan's recorded lights-off
 * before the lamp pass, no ruler, no 0xD7.
 *
 * THE DUAL TILE, KEPT FOR THE NEXT READER. The table opens the reader anew
 * for every row (-N: ArgyllCMS restores its own white from its calibration
 * file), so the tile's UV-LED reading T is kept beside that file, in
 * ArgyllCMS's own folder: ".i1p_<serial>.cqdual<mode>". It holds T, the
 * integration and the white calibration's date and a checksum of its white
 * reading; it is used again ONLY for the white calibration it was made with
 * (the same date, the same white), so a new white makes a new dual tile
 * necessary. kA / kD (the factory tables) are never written anywhere. */

/* CQ_TDUAL_PASS_LAMP / _UV and CQ_TDUAL_NMAX (1150 readings: the longest
 * recorded UV-LED on time, 6.0 s, a slow hand pass) are in cq_dual.h. */
#define CQ_TDUAL_UV_FLAGS CQ_DUAL_FORM_UV_TILE	/* 0x0200: the recorded UV pass on the table (no scan bit) */
#define CQ_TDUAL_FILE_MAGIC "CQDUAL01"

/* the recorded UV pass must be a form the dual scan's gate allows */
typedef char cq_tdual_form_check[(CQ_TDUAL_UV_FLAGS == CQ_DUAL_FORM_UV_TILE
                                  && CQ_TSCAN_LAMPCLOCKS == CQ_DUAL_UV_LAMPCLOCKS) ? 1 : -1];

/* tests only: the dual tile file's path (NULL = ArgyllCMS's own folder) */
const char *i1pro2_cq_dual_tile_path_for_test = NULL;

static int cq_tdual_lamp_done = 0;	/* the last pass was a dual lamp pass that delivered */

/* The table dual session on: the factory tables (read-only copies), and NO
 * ruler (the table reads none; the hand dual scan's ruler is left off). */
int i1pro2_cq_tdual_on(void *pp, double *kA, double *kD) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	int r = i1pro2_cq_dual_options(pp, 1, kA, kD);
	if (p != NULL && (m = (i1proimp *)p->m) != NULL)
		m->cq_ruler_on = 0;
	cq_tdual_lamp_done = 0;
	return r;
}

static unsigned int cq_tdual_white_sum(i1proimp *m, i1pro_state *s) {
	const unsigned char *b;
	unsigned int h = 2166136261u;
	size_t k, n;
	if (s->white_data == NULL)
		return 0;
	b = (const unsigned char *)(s->white_data - 1);
	n = sizeof(double) * (size_t)(m->nraw + 1);
	for (k = 0; k < n; k++) {
		h ^= b[k];
		h *= 16777619u;
	}
	return h;
}

static int cq_tdual_path(i1proimp *m, char **out, char ***paths, int *np, int write) {
	char name[100];
	*paths = NULL;
	*np = 0;
	if (i1pro2_cq_dual_tile_path_for_test != NULL) {
		*out = (char *)i1pro2_cq_dual_tile_path_for_test;
		return 1;
	}
	sprintf(name, "ArgyllCMS/.i1p_%d.cqdual%d", m->serno, m->mmode);
	if ((*np = xdg_bds(NULL, paths, xdg_cache, write ? xdg_write : xdg_read, xdg_user,
	                   xdg_none, name)) < 1)
		return 0;
	*out = (*paths)[0];
	return 1;
}

/* Keep this tile reading for the next reader of the same white calibration. */
int i1pro2_cq_dual_tile_save(void *pp, const cq_dual_tile *t) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	i1pro_state *s;
	char *path = NULL, **paths = NULL;
	int np = 0, ok = 0, v = 1;
	long long cf;
	unsigned int sum;
	FILE *fp;
	if (cq_dual_s(pp) == NULL || t == NULL || !t->ok)
		return 0;
	m = (i1proimp *)p->m;
	s = &m->ms[m->mmode];
	if (!s->cal_valid || m->highres || !cq_tdual_path(m, &path, &paths, &np, 1))
		return 0;
	if (i1pro2_cq_dual_tile_path_for_test == NULL && create_parent_directories(path)) {
		xdg_free(paths, np);
		return 0;
	}
	if ((fp = fopen(path, "wb")) != NULL) {
		cf = (long long)s->cfdate;
		sum = cq_tdual_white_sum(m, s);
		ok = fwrite(CQ_TDUAL_FILE_MAGIC, 1, 8, fp) == 8
		  && fwrite(&v, sizeof(int), 1, fp) == 1
		  && fwrite(&m->mmode, sizeof(int), 1, fp) == 1
		  && fwrite(&cf, sizeof(cf), 1, fp) == 1
		  && fwrite(&sum, sizeof(sum), 1, fp) == 1
		  && fwrite(&t->lamp_clocks, sizeof(int), 1, fp) == 1
		  && fwrite(&t->uv_clocks, sizeof(int), 1, fp) == 1
		  && fwrite(&t->mode_scan, sizeof(int), 1, fp) == 1
		  && fwrite(t->T, sizeof(double), CQ_DUAL_BANDS, fp) == CQ_DUAL_BANDS;
		if (fclose(fp) != 0)
			ok = 0;
	}
	if (paths != NULL)
		xdg_free(paths, np);
	return ok;
}

/* W and E of the CURRENT white calibration (as i1pro2_cq_dual_tile works
 * them out), for a kept T. */
static void cq_tdual_we(i1pro *p, i1proimp *m, i1pro_state *s, cq_dual_tile *out) {
	double **ww, **wa;
	int j, j2;
	if (i1pro2_cq_dual_noproc_for_test)
		return;
	ww = dmatrix(0, 0, -1, m->nraw - 1);
	wa = dmatrix(0, 0, 0, m->nwav[0] - 1);
	for (j2 = -1; j2 < m->nraw; j2++)
		ww[0][j2] = s->white_data[j2];
	i1pro_absraw_to_abswav(p, 0, s->reflective, 1, wa, ww);
	for (j = 0; j < CQ_DUAL_BANDS; j++) {
		out->W[j] = j < m->nwav[0] ? wa[0][j] * s->cal_factor[0][j] : 0.0;
		out->E[j] = j < m->nwav[0] && s->cal_factor[0][j] != 0.0
		          ? m->emis_coef[0][j] / s->cal_factor[0][j] : 0.0;
	}
	free_dmatrix(ww, 0, 0, -1, m->nraw - 1);
	free_dmatrix(wa, 0, 0, 0, m->nwav[0] - 1);
}

/* The kept tile reading of THIS white calibration (restored by ArgyllCMS
 * from its file): 1 = out is a dual calibration as i1pro2_cq_dual_tile
 * would give it (no volts); 0 = none, or not of this white. Reads only. */
int i1pro2_cq_dual_tile_restore(void *pp, cq_dual_tile *out) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	i1pro_state *s;
	char *path = NULL, **paths = NULL, magic[8];
	int np = 0, ok = 0, v = 0, mode = -1, lc = 0, uc = 0, ms = 0, clk;
	long long cf = 0;
	unsigned int sum = 0;
	double T[CQ_DUAL_BANDS];
	FILE *fp;
	if (out == NULL)
		return 0;
	memset(out, 0, sizeof(*out));
	out->volts_before = out->volts_after = -1;
	if (cq_dual_s(pp) == NULL)
		return 0;
	m = (i1proimp *)p->m;
	s = &m->ms[m->mmode];
	if (!s->reflective || !s->cal_valid || m->highres || !cq_tdual_path(m, &path, &paths, &np, 0))
		return 0;
	if ((fp = fopen(path, "rb")) != NULL) {
		ok = fread(magic, 1, 8, fp) == 8 && memcmp(magic, CQ_TDUAL_FILE_MAGIC, 8) == 0
		  && fread(&v, sizeof(int), 1, fp) == 1 && v == 1
		  && fread(&mode, sizeof(int), 1, fp) == 1
		  && fread(&cf, sizeof(cf), 1, fp) == 1
		  && fread(&sum, sizeof(sum), 1, fp) == 1
		  && fread(&lc, sizeof(int), 1, fp) == 1
		  && fread(&uc, sizeof(int), 1, fp) == 1
		  && fread(&ms, sizeof(int), 1, fp) == 1
		  && fread(T, sizeof(double), CQ_DUAL_BANDS, fp) == CQ_DUAL_BANDS;
		fclose(fp);
	}
	if (paths != NULL)
		xdg_free(paths, np);
	if (!ok)
		return 0;
	clk = m->intclkp > 0.0 ? (int)floor(s->inttime / m->intclkp + 0.5) : -1;
	/* only for the white it was made with: the same mode, date, white, exposure */
	if (mode != m->mmode || cf != (long long)s->cfdate || sum != cq_tdual_white_sum(m, s)
	 || ms != s->scan || uc != clk || lc != clk)
		return 0;
	memcpy(out->T, T, sizeof(T));
	cq_tdual_we(p, m, s, out);
	out->lamp_clocks = lc;
	out->uv_clocks = uc;
	out->mode_scan = ms;
	out->ok = 1;
	return 1;
}

/* One 0xD4 of the table's dual row (the table scan's own trigger, plus the
 * host's lamp bookkeeping for a UV-LED reading as ArgyllCMS's UV mode keeps
 * it: no lamp). */
static i1pro_code cq_tdual_trigger(i1pro *p, int lampclocks, int nmeas, int flags2, int nolamp) {
	i1proimp *m = (i1proimp *)p->m;
	m->intclkp = m->intclkp2;
	m->subclkdiv = m->subclkdiv2;
	m->subtmode = 0;
	m->c_intclocks = CQ_TSCAN_INTCLOCKS;
	m->c_lampclocks = lampclocks;
	m->c_nummeas = nmeas;
	m->c_measmodeflags = I1PRO_MMF_LOWGAIN | (nolamp ? I1PRO_MMF_NOLAMP : 0);
	m->c_measmodeflags2 = flags2;
	m->c_inttime = CQ_TSCAN_INTCLOCKS * m->intclkp;
	m->c_lamptime = lampclocks * m->subclkdiv * m->intclkp;
	usb_reinit_cancel(&m->rd_sync);
	return i1pro2_triggermeasure(p, TRIG_DELAY);
}

/* Can pass *pass* of nread readings be fired NOW (the table's scan move is
 * sent only after a yes)? 1 yes; 0 not yet (*wait_ms); -1 never (why). The
 * lamp pass: the table scan's own rules (cq_tscan.h). The UV pass: right
 * after this row's lamp pass delivered, never after anything else; no
 * lights-off (none was recorded before it); the lamp dark for the recorded
 * spacing. Both: a dual session with a dual tile, at most CQ_TDUAL_NMAX. */
int i1pro2_cq_tdual_ready(void *pp, int pass, int nread, int have_tile, int *wait_ms,
                          char *why, int whylen) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	i1pro_state *s;
	int lampoff = i1pro2_cq_tscan_lampoff_ms_for_test > 0
	            ? i1pro2_cq_tscan_lampoff_ms_for_test : CQ_TSCAN_LAMPOFF_MS;
	int w = 0, since;
	time_t now = time(NULL);
	if (wait_ms != NULL)
		*wait_ms = 0;
#define CQ_TD_NO(txt) do { if (why != NULL && whylen > 0) { strncpy(why, txt, whylen - 1); why[whylen - 1] = '\0'; } return -1; } while (0)
	if (cq_dual_s(pp) == NULL || cq_tscan_m(pp) == NULL)
		CQ_TD_NO("not a table dual session");
	if (!have_tile)
		CQ_TD_NO("no dual calibration");
	if (nread < CQ_TSCAN_NMIN || nread > CQ_TDUAL_NMAX)
		CQ_TD_NO("reading count out of range");
	if (pass == CQ_TDUAL_PASS_LAMP)
		return i1pro2_cq_tscan_ready(pp, nread, wait_ms, why, whylen);
	if (pass != CQ_TDUAL_PASS_UV)
		CQ_TD_NO("no such pass");
	m = (i1proimp *)p->m;
	if (m->cq_lights != 0 || m->cq_ruler_on)
		CQ_TD_NO("the lights or ruler Beta is in use");
	s = &m->ms[m->mmode];
	if (!s->reflective || !s->scan || s->emiss || s->trans || s->flash || m->uv_en)
		CQ_TD_NO("not in reflective strip mode");
	if (!s->cal_valid)
		CQ_TD_NO("not calibrated");
	if ((now - s->cfdate) > (WCALTOUT - CQ_TSCAN_CAL_SPARE_S))
		CQ_TD_NO("the calibration is about to expire");
	if (m->trig_thread != NULL && m->tr_t2 == 0)
		CQ_TD_NO("a trigger is still pending");
	if (!cq_tdual_lamp_done)
		CQ_TD_NO("the lamp pass of this row did not deliver");
#undef CQ_TD_NO
	since = (int)(msec_time() - m->llamponoff);
	if (since < lampoff)
		w = lampoff - since;
	if (wait_ms != NULL)
		*wait_ms = w;
	if (why != NULL && whylen > 0)
		why[0] = '\0';
	return w > 0 ? 0 : 1;
}

/* Fire one pass of a dual row. NO cancellation point and no wait: once
 * entered, the pass's lit trigger (the lamp, or the UV LED) is attempted
 * FIRST, because the table's pending scan move waits for it; then (lamp)
 * the status read, then the 5 dark readings, then (UV) the volts. Then the
 * readings are processed as the table scan's are (the dark of this pass,
 * every reading on its own, the lamp white's factor): a UV pass's spectra
 * are therefore in lamp-white units, as the dual formula wants U. Returns 0
 * when both readings arrived; -1 when nothing was sent (never after the
 * scan move: the arm step checked the same). */
int i1pro2_cq_tdual_fire(void *pp, int pass, int nread, int npatch, cq_tscan_rec *r,
                         int *volts_before, int *volts_after) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_tscan_m(pp);
	i1pro_state *s;
	i1pro_code ev;
	double inttime;
	int nsb, i, j, uv = pass == CQ_TDUAL_PASS_UV;

	memset(r, 0, sizeof(*r));
	if (volts_before != NULL) *volts_before = -1;
	if (volts_after != NULL) *volts_after = -1;
	r->t_fire = msec_time();
	r->nread = nread;
	r->dark_ev = r->lit_ev = r->misc_ev = I1PRO_INT_NOTCALIBRATED;
	if (m == NULL || cq_dual_s(pp) == NULL || nread < CQ_TSCAN_NMIN || nread > CQ_TDUAL_NMAX
	 || (pass != CQ_TDUAL_PASS_LAMP && pass != CQ_TDUAL_PASS_UV))
		return -1;		/* nothing was sent */
	if (uv && (!cq_tdual_lamp_done
	        || i1pro2_cq_dual_form_refused(pp, CQ_TDUAL_UV_FLAGS, CQ_TSCAN_LAMPCLOCKS)))
		return -1;		/* nothing was sent (the arm refused the same before the move) */
	cq_tdual_lamp_done = 0;
	s = &m->ms[m->mmode];
	nsb = m->nsen * 2;
	r->since_lamp_off_ms = r->t_fire - m->llamponoff;
	r->since_lights_off_ms = cq_tscan_off_end != 0 ? r->t_fire - cq_tscan_off_end : 0;
	cq_tscan_off_end = 0;		/* the next lamp pass needs its own */

	r->raw_dark = (unsigned char *)calloc(CQ_TSCAN_DARK_N, nsb);
	r->raw_lit = (unsigned char *)calloc(nread, nsb);

	/* ---- from here on: no return before the lit trigger was attempted ---- */
	if (r->raw_lit == NULL)
		r->lit_ev = I1PRO_INT_MALLOC;
	else if ((r->lit_ev = cq_tdual_trigger(p, CQ_TSCAN_LAMPCLOCKS, nread,
	                                       uv ? CQ_TDUAL_UV_FLAGS : CQ_TSCAN_FLAGS_LIT, uv))
	                                                                   == I1PRO_OK)
		r->lit_ev = i1pro_readmeasurement(p, nread, 0, r->raw_lit, nread * nsb, NULL, i1p_norm);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
	if (uv) {
		cq_dual_state *st = cq_dual_s(pp);
		if (st != NULL)
			st->uv_lit = 0;		/* a non-scan reading of nread readings: over */
	}
	r->lit_sent = m->tr_t2 != 0;
	r->t_lit_trig = m->tr_t1;
	r->t_lit_data = m->tr_t7;
	/* ---- the lit trigger has been attempted ---- */
	if (r->lit_ev == I1PRO_OK) {
		r->ngot = nread;
		r->raw_lit_len = nread * nsb;
	}
	if (!uv) {		/* the status read after every recorded lamp pass (0xC9, 8 bytes in) */
		r->misc_ev = i1pro_getmisc(p, &r->misc[0], &r->misc[1], &r->misc[2], &r->misc[3],
		                           &r->misc[4]);
		r->t_misc = msec_time();
	} else
		r->misc_ev = I1PRO_OK;

	/* the dark of this pass, AFTER it (as recorded on the table's dual rows):
	 * the table's move is under way already, so ArgyllCMS's own read (its
	 * normal timeout) reads it; no USB call of this file's own */
	if (r->raw_dark == NULL)
		r->dark_ev = I1PRO_INT_MALLOC;
	else if ((r->dark_ev = cq_tdual_trigger(p, 0, CQ_TSCAN_DARK_N, CQ_TSCAN_FLAGS_DARK, 1))
	                                                                       == I1PRO_OK)
		r->dark_ev = i1pro_readmeasurement(p, CQ_TSCAN_DARK_N, 0, r->raw_dark,
		                                   CQ_TSCAN_DARK_N * nsb, NULL, i1p_dark_cal);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
	r->dark_sent = m->tr_t2 != 0;
	r->t_dark_trig = m->tr_t1;
	r->t_dark_data = m->tr_t7;
	if (r->dark_ev == I1PRO_OK)
		r->raw_dark_len = CQ_TSCAN_DARK_N * nsb;
	if (uv)		/* the UV LED's volts after each UV pass, as recorded (read only) */
		cq_dual_volts(p, volts_before != NULL ? volts_before : &i,
		              volts_after != NULL ? volts_after : &j);

	if (r->dark_ev != I1PRO_OK || r->lit_ev != I1PRO_OK)
		return 1;
	if (!uv)
		cq_tdual_lamp_done = 1;		/* the UV pass of this row may be armed now */
	if (i1pro2_cq_tscan_noproc_for_test)
		return 0;

	/* ---- processing: the table scan's own steps ---- */
	inttime = CQ_TSCAN_INTCLOCKS * m->intclkp2;
	for (i = 0; i < r->ngot; i++)
		for (j = 0; j < m->nsen; j++) {
			int v = (r->raw_lit[i * nsb + 2 * j] << 8) | r->raw_lit[i * nsb + 2 * j + 1];
			if (v > r->maxraw)
				r->maxraw = v;
		}
	r->saturated = r->maxraw >= m->sens_sat0;
	{
		double *dark = dvectorz(-1, m->nraw - 1);
		double **mm = dmatrix(0, r->ngot - 1, -1, m->nraw - 1);
		double darkthresh = m->sens_dark + inttime * 900.0;
		r->nwav = m->nwav[m->highres];
		r->wl_short = m->wl_short[m->highres];
		r->wl_long = m->wl_long[m->highres];
		r->dark_proc_ev = i1pro_dark_measure_2(p, dark, CQ_TSCAN_DARK_N, inttime, 0,
		                                       r->raw_dark, r->raw_dark_len);
		if ((ev = i1pro_sens_to_absraw(p, mm, r->raw_lit, r->ngot, inttime, 0, &darkthresh))
		                                                                   == I1PRO_OK) {
			double **sp = dmatrix(0, r->ngot - 1, 0, r->nwav - 1);
			i1pro_sub_absraw(p, r->ngot, inttime, 0, mm, dark);
			/* every reading on its own; the recogniser is not asked for a UV pass */
			i1pro_absraw_to_abswav(p, m->highres, s->reflective, r->ngot, sp, mm);
			i1pro_scale_specrd(p, sp, r->ngot, sp);
			if ((r->spec = (double *)malloc(sizeof(double) * r->ngot * r->nwav)) != NULL)
				for (i = 0; i < r->ngot; i++)
					memcpy(r->spec + i * r->nwav, sp[i], sizeof(double) * r->nwav);
			free_dmatrix(sp, 0, r->ngot - 1, 0, r->nwav - 1);
		} else
			r->lit_ev = ev;
		free_dmatrix(mm, 0, r->ngot - 1, -1, m->nraw - 1);
		free_dvector(dark, -1, m->nraw - 1);
	}
	(void)npatch;
	return r->lit_ev == I1PRO_OK ? 0 : 1;
}
