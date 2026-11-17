/* CHROMIQ: the i1Pro 2 "table scan" (X-Rite i1iO 2, study, 2026-11-16).
 * The code; the description, the recorded bytes and the API are in
 * cq_tscan.h. ChromIQ's own file, not part of ArgyllCMS; included ONCE, at
 * the end of i1pro_imp.c (its static trigger and read functions are used),
 * after the light sequences (cq_lights_seq_off_slow is reused, byte for byte
 * the recorded OFF_SLOW). scripts/vendor_instlib.py never writes this file.
 *
 * Off (the helper not started with --i1io-table-scan) nothing here is ever
 * called: no Argyll code path reaches it. */

#include "cq_tscan.h"

int i1pro2_cq_tscan_lampoff_ms_for_test = 0;
int i1pro2_cq_tscan_lightsoff_ms_for_test = 0;
int i1pro2_cq_tscan_noproc_for_test = 0;

/* The one helper process has one instrument; when the last lights-off of
 * this pass ended (0 = none since the last fire). */
static unsigned int cq_tscan_off_end = 0;

static i1proimp *cq_tscan_m(void *pp) {
	i1pro *p = (i1pro *)pp;
	if (p == NULL || p->dtype != instI1Pro2 || !p->inited || p->icom == NULL)
		return NULL;
	return (i1proimp *)p->m;
}

int i1pro2_cq_tscan_lights_off(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_tscan_m(pp);
	unsigned char pbuf[4];
	int wbytes = 0, se;
	int size = (int)sizeof(cq_lights_seq_off_slow);
	if (m == NULL)
		return ICOM_SYS;
	int2buf(pbuf, size);
	se = p->icom->usb_control(p->icom,
		               IUSB_ENDPOINT_OUT | IUSB_REQ_TYPE_VENDOR | IUSB_REQ_RECIP_DEVICE,
	                   0xD6, 0, 0, pbuf, 4, NULL, 0.25);
	if (icoms2i1pro_err(se) == I1PRO_OK)
		se = p->icom->usb_write(p->icom, NULL, 0x03, (unsigned char *)cq_lights_seq_off_slow,
		                        size, &wbytes, 0.25);
	/* the quiet time counts from the END of the write, done or not */
	if ((cq_tscan_off_end = msec_time()) == 0)
		cq_tscan_off_end = 1;
	if (icoms2i1pro_err(se) == I1PRO_OK && wbytes != size)
		se = ICOM_SHORT;
	return icoms2i1pro_err(se) == I1PRO_OK ? 0 : se;
}

int i1pro2_cq_tscan_ready(void *pp, int nread, int *wait_ms, char *why, int whylen) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_tscan_m(pp);
	i1pro_state *s;
	int lampoff = i1pro2_cq_tscan_lampoff_ms_for_test > 0
	            ? i1pro2_cq_tscan_lampoff_ms_for_test : CQ_TSCAN_LAMPOFF_MS;
	int lightsoff = i1pro2_cq_tscan_lightsoff_ms_for_test > 0
	              ? i1pro2_cq_tscan_lightsoff_ms_for_test : CQ_TSCAN_LIGHTSOFF_MS;
	int w = 0, since;
	time_t now = time(NULL);

	if (wait_ms != NULL)
		*wait_ms = 0;
#define CQ_TS_NO(txt) do { if (why != NULL && whylen > 0) { strncpy(why, txt, whylen - 1); why[whylen - 1] = '\0'; } return -1; } while (0)
	if (m == NULL)
		CQ_TS_NO("not an open i1Pro 2");
	if (m->cq_lights != 0 || m->cq_ruler_on)
		CQ_TS_NO("the lights or ruler Beta is in use");
	if (nread < CQ_TSCAN_NMIN || nread > CQ_TSCAN_NMAX)
		CQ_TS_NO("reading count out of range");
	s = &m->ms[m->mmode];
	if (!s->reflective || !s->scan || s->emiss || s->trans || s->flash || m->uv_en)
		CQ_TS_NO("not in reflective strip mode");
	if (!s->cal_valid)
		CQ_TS_NO("not calibrated");
	if ((now - s->cfdate) > (WCALTOUT - CQ_TSCAN_CAL_SPARE_S))
		CQ_TS_NO("the calibration is about to expire");
	if (m->trig_thread != NULL && m->tr_t2 == 0)
		CQ_TS_NO("a trigger is still pending");
	if (cq_tscan_off_end == 0)
		CQ_TS_NO("the lights-off of this pass was not sent");
#undef CQ_TS_NO
	since = (int)(msec_time() - m->llamponoff);
	if (since < lampoff && lampoff - since > w)
		w = lampoff - since;
	since = (int)(msec_time() - cq_tscan_off_end);
	if (since < lightsoff && lightsoff - since > w)
		w = lightsoff - since;
	if (wait_ms != NULL)
		*wait_ms = w;
	if (why != NULL && whylen > 0)
		why[0] = '\0';
	(void)p;
	return w > 0 ? 0 : 1;
}

/* One 0xD4 exactly as recorded, through ArgyllCMS's own delayed trigger
 * (the read is submitted first, the trigger thread sends the 0xD4 as soon as
 * it is pending). No lamp-off sleep, no lights, no ruler bits. */
static i1pro_code cq_tscan_trigger(i1pro *p, int lampclocks, int nmeas, int flags2) {
	i1proimp *m = (i1proimp *)p->m;
	m->intclkp = m->intclkp2;
	m->subclkdiv = m->subclkdiv2;
	m->subtmode = 0;
	m->c_intclocks = CQ_TSCAN_INTCLOCKS;
	m->c_lampclocks = lampclocks;
	m->c_nummeas = nmeas;
	m->c_measmodeflags = I1PRO_MMF_LOWGAIN | (lampclocks > 0 ? 0 : I1PRO_MMF_NOLAMP);
	m->c_measmodeflags2 = flags2;
	m->c_inttime = CQ_TSCAN_INTCLOCKS * m->intclkp;
	m->c_lamptime = lampclocks * m->subclkdiv * m->intclkp;
	usb_reinit_cancel(&m->rd_sync);
	return i1pro2_triggermeasure(p, TRIG_DELAY);
}

void cq_tscan_rec_clear(cq_tscan_rec *r) {
	if (r == NULL)
		return;
	free(r->raw_dark);
	free(r->raw_lit);
	free(r->spec);
	free(r->rec_spec);
	memset(r, 0, sizeof(*r));
}

int i1pro2_cq_tscan_fire(void *pp, int nread, int npatch, cq_tscan_rec *r) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_tscan_m(pp);
	i1pro_state *s;
	i1pro_code ev;
	double inttime;
	int nsb, i, j;

	memset(r, 0, sizeof(*r));
	r->t_fire = msec_time();
	r->nread = nread;
	r->dark_ev = r->lit_ev = r->misc_ev = I1PRO_INT_NOTCALIBRATED;
	if (m == NULL || nread < CQ_TSCAN_NMIN || nread > CQ_TSCAN_NMAX)
		return -1;		/* nothing was sent */
	s = &m->ms[m->mmode];
	nsb = m->nsen * 2;
	r->since_lamp_off_ms = r->t_fire - m->llamponoff;
	r->since_lights_off_ms = cq_tscan_off_end != 0 ? r->t_fire - cq_tscan_off_end : 0;
	cq_tscan_off_end = 0;		/* the next pass needs its own */

	r->raw_dark = (unsigned char *)calloc(CQ_TSCAN_DARK_N, nsb);
	r->raw_lit = (unsigned char *)calloc(nread, nsb);

	/* ---- from here on: no return before the lit trigger was attempted ---- */
	if (r->raw_dark == NULL)
		r->dark_ev = I1PRO_INT_MALLOC;
	else if ((r->dark_ev = cq_tscan_trigger(p, 0, CQ_TSCAN_DARK_N, CQ_TSCAN_FLAGS_DARK)) == I1PRO_OK) {
		/* The dark's read with a SHORT timeout (recorded: its data came 38-45 ms
		 * after the trigger): ArgyllCMS's own read would wait 2 s before giving
		 * up, and the lamp trigger after it is what the table is waiting for. */
		int rwbytes = 0, se;
		m->tr_t3 = msec_time();
		se = p->icom->usb_read(p->icom, &m->rd_sync, 0x82, r->raw_dark,
		                       CQ_TSCAN_DARK_N * nsb, &rwbytes, CQ_TSCAN_DARK_TOUT);
		m->tr_t7 = msec_time();
		if ((r->dark_ev = icoms2i1pro_err(se)) != I1PRO_OK && m->trig_rv != I1PRO_OK)
			r->dark_ev = m->trig_rv;
		else if (r->dark_ev == I1PRO_OK && rwbytes != CQ_TSCAN_DARK_N * nsb)
			r->dark_ev = I1PRO_HW_ME_SHORTREAD;
	}
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);	/* joins: its 0xD4 is out or failed */
		m->trig_thread = NULL;
	}
	r->dark_sent = m->tr_t2 != 0;
	r->t_dark_trig = m->tr_t1;
	r->t_dark_data = m->tr_t7;
	if (r->dark_ev == I1PRO_OK)
		r->raw_dark_len = CQ_TSCAN_DARK_N * nsb;

	if (r->raw_lit == NULL)
		r->lit_ev = I1PRO_INT_MALLOC;
	else if ((r->lit_ev = cq_tscan_trigger(p, CQ_TSCAN_LAMPCLOCKS, nread, CQ_TSCAN_FLAGS_LIT)) == I1PRO_OK)
		r->lit_ev = i1pro_readmeasurement(p, nread, 0, r->raw_lit, nread * nsb, NULL, i1p_norm);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
	r->lit_sent = m->tr_t2 != 0;
	r->t_lit_trig = m->tr_t1;
	r->t_lit_data = m->tr_t7;
	/* ---- the lamp trigger has been attempted ---- */

	if (r->lit_ev == I1PRO_OK) {
		r->ngot = nread;
		r->raw_lit_len = nread * nsb;
	}
	/* The status read i1Profiler makes after every pass (0xC9, 8 bytes in). */
	r->misc_ev = i1pro_getmisc(p, &r->misc[0], &r->misc[1], &r->misc[2], &r->misc[3], &r->misc[4]);
	r->t_misc = msec_time();

	if (r->dark_ev != I1PRO_OK || r->lit_ev != I1PRO_OK)
		return 1;
	if (i1pro2_cq_tscan_noproc_for_test)
		return 0;

	/* ---- processing: ArgyllCMS's own steps, as a strip read makes them ---- */
	inttime = CQ_TSCAN_INTCLOCKS * m->intclkp2;
	for (i = 0; i < r->ngot; i++) {
		for (j = 0; j < m->nsen; j++) {
			int v = (r->raw_lit[i * nsb + 2 * j] << 8) | r->raw_lit[i * nsb + 2 * j + 1];
			if (v > r->maxraw)
				r->maxraw = v;
		}
	}
	r->saturated = r->maxraw >= m->sens_sat0;
	{
		double *dark = dvectorz(-1, m->nraw - 1);
		double **mm = dmatrix(0, r->ngot - 1, -1, m->nraw - 1);
		double darkthresh = m->sens_dark + inttime * 900.0;
		double satthresh;
		r->nwav = m->nwav[m->highres];
		r->wl_short = m->wl_short[m->highres];
		r->wl_long = m->wl_long[m->highres];
		/* the dark of this pass (i1pro_dark_measure_2: average and checks) */
		r->dark_proc_ev = i1pro_dark_measure_2(p, dark, CQ_TSCAN_DARK_N, inttime, 0,
		                                       r->raw_dark, r->raw_dark_len);
		if ((ev = i1pro_sens_to_absraw(p, mm, r->raw_lit, r->ngot, inttime, 0, &darkthresh))
		                                                                   == I1PRO_OK) {
			i1pro_sub_absraw(p, r->ngot, inttime, 0, mm, dark);
			satthresh = i1pro_raw_to_absraw(p, m->sens_sat0, inttime, 0);
			/* ArgyllCMS's recogniser, on a copy: a cross-check only */
			if (npatch > 0 && npatch <= r->ngot) {
				double **cp = dmatrix(0, r->ngot - 1, -1, m->nraw - 1);
				double **pa = dmatrix(0, npatch - 1, -1, m->nraw - 1);
				int flags = 0;
				for (i = 0; i < r->ngot; i++)
					memcpy(&cp[i][-1], &mm[i][-1], sizeof(double) * (m->nraw + 1));
				r->npatch = npatch;
				r->rec_ev = i1pro_extract_patches_multimeas(p, &flags, pa, npatch, cp,
				                                            r->ngot, NULL, satthresh, inttime);
				if (r->rec_ev == I1PRO_OK && (flags & 3) == 0) {
					double **ps = dmatrix(0, npatch - 1, 0, r->nwav - 1);
					i1pro_absraw_to_abswav(p, m->highres, s->reflective, npatch, ps, pa);
					i1pro_scale_specrd(p, ps, npatch, ps);
					if ((r->rec_spec = (double *)malloc(sizeof(double) * npatch * r->nwav)) != NULL)
						for (i = 0; i < npatch; i++)
							memcpy(r->rec_spec + i * r->nwav, ps[i], sizeof(double) * r->nwav);
					free_dmatrix(ps, 0, npatch - 1, 0, r->nwav - 1);
				} else if (r->rec_ev == I1PRO_OK)
					r->rec_ev = (flags & 1) ? I1PRO_RD_READINCONS : I1PRO_RD_SENSORSATURATED;
				free_dmatrix(pa, 0, npatch - 1, -1, m->nraw - 1);
				free_dmatrix(cp, 0, r->ngot - 1, -1, m->nraw - 1);
			}
			/* every reading on its own (as i1pro_read_patches_2a) */
			{
				double **sp = dmatrix(0, r->ngot - 1, 0, r->nwav - 1);
				i1pro_absraw_to_abswav(p, m->highres, s->reflective, r->ngot, sp, mm);
				i1pro_scale_specrd(p, sp, r->ngot, sp);
				if ((r->spec = (double *)malloc(sizeof(double) * r->ngot * r->nwav)) != NULL)
					for (i = 0; i < r->ngot; i++)
						memcpy(r->spec + i * r->nwav, sp[i], sizeof(double) * r->nwav);
				free_dmatrix(sp, 0, r->ngot - 1, 0, r->nwav - 1);
			}
		} else
			r->lit_ev = ev;
		free_dmatrix(mm, 0, r->ngot - 1, -1, m->nraw - 1);
		free_dvector(dark, -1, m->nraw - 1);
	}
	return r->lit_ev == I1PRO_OK ? 0 : 1;
}
