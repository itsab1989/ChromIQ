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
 *   * the UV readings' pre-delay: the lamp's (s->lamptime -> lamp clocks),
 *     as i1Profiler sends 41 clocks for its lamp AND its UV readings.
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

/* i1pro_trigger_one_measure: the lamp pre-delay for a UV-LED reading of the
 * dual scan (as recorded: i1Profiler sends the lamp's 41 clocks with its UV
 * readings too). Counts the UV triggers. */
int i1pro2_cq_dual_lamp_delay(void *pp, int mmodif) {
	cq_dual_state *st = cq_dual_s(pp);
	if (st == NULL || (mmodif != i1p2_UV && mmodif != i1p2_cq_UV_cal))
		return 0;
	st->uv_triggers++;
	st->uv_lit = 1;
	return 1;
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
	if (st->phase == CQ_DUAL_PHASE_UV && mmodif == i1p2_UV && m->cq_ruler_th != NULL
	 && st->lamp_readings > 0) {
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
	n = nmeas < CQ_DUAL_MAX_UV_READINGS ? nmeas : CQ_DUAL_MAX_UV_READINGS;
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
			absraw[i][j] = n > 0 ? multimes[0][j] : 0.0;
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
