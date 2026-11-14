/* CHROMIQ_EXT: Beta parts PAUSED on the i1Pro 2 in ChromIQ 4.3.36
 * (2026-11-14, interim; ~/Desktop/ChromIQ-work/2026-11-14_lights_comm_loss).
 *
 * A tester with a real i1Pro 2 (4.3.34, Windows) found that, with the lights
 * option's result signals on, the strip after every accepted one ended with
 * "The instrument lost communication with the computer". The likely cause
 * (not proven): the 2-second off program swapped in over a RUNNING pulse
 * program and a measure trigger about 10 ms later, a step neither i1Profiler
 * nor ChromIQ 4.3.33 ever sent. "Left on during a reading" has the same step
 * before a calibration (the off over the pulse that is the ready light), and
 * the ruler check has never run on a real instrument. Until a tester has
 * confirmed a fix, an i1Pro 2 gets, whatever the stored choices:
 *   - the lights as with both choices off (4.3.33's recorded bytes: the
 *     steady white, the off over the white, the off at the close);
 *   - no ruler check (exactly the option-off wire).
 * The i1Pro 3 is not affected. Python cannot decide this: the generation is
 * known only once the driver has opened the instrument (i1Pro and i1Pro 2
 * share one USB id), so the helper does, here, in one place.
 * AGPL-3.0 like the rest of the helper (see ../instlib/License.txt). */
#ifndef CQ_BETA_PAUSE_H
#define CQ_BETA_PAUSE_H

#define CQ_PAUSED_SIGNALS 1		/* "Ready light and result signals" */
#define CQ_PAUSED_LEFT_ON 2		/* "Left on during a reading" */

/* The lights choices generation `gen` (2 = i1Pro 2, 3 = i1Pro 3) is given
 * for the ones asked for; returns which asked-for ones are paused. */
static inline int cq_lights_choices_for(int gen, int signals, int left_on,
                                        int *sig_out, int *left_out) {
	int paused = 0;
	*sig_out = signals;
	*left_out = left_on;
	if (gen == 2) {
		if (signals)
			paused |= CQ_PAUSED_SIGNALS;
		if (left_on)
			paused |= CQ_PAUSED_LEFT_ON;
		*sig_out = 0;
		*left_out = 0;
	}
	return paused;
}

/* Whether the ruler check is paused for generation `gen`. */
static inline int cq_ruler_paused_for(int gen) {
	return gen == 2;
}

#endif /* CQ_BETA_PAUSE_H */
