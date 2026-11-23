/* CHROMIQ: the wavelength offset the i1Pro 2's filters use, REPORTED
 * (ChromIQ 4.3.59).
 *
 * ChromIQ's own file, not part of ArgyllCMS; scripts/vendor_instlib.py never
 * writes it. Included once at the end of i1pro_imp.c, because it uses that
 * file's static i1pro_raw2wav_uncal (the same conversion ArgyllCMS logs its
 * "correction %f nm" with).
 *
 * Why: a tester's i1iO table strips showed a -1.25 nm shift. Every table row
 * is a new helper process that does not calibrate; it reads with what
 * i1pro_restore_calibration restored when the instrument was opened, and the
 * filters are recomputed with the restored offset only when mode 0's
 * wavelength calibration was restored (i1pro_imp_init). A file that fails its
 * identification, or a mode whose settings differ, leaves the EEPROM's
 * factory filters, and ArgyllCMS says so only in its debug log. The helper
 * now prints one "wavelength" event with what this function returns.
 *
 * READS ONLY. It reads the driver's state and the i1pro_cq_wl_* variables the
 * 4.3.59 patches write (scripts/vendor_instlib.py, I1PRO_IMP_C_WL_459). It
 * sends no USB request, reads or writes no EEPROM, changes no driver state
 * and no file. AGPL-3.0 / GPLv2+ like the rest of the library. */

static const char *cq_wl_restore_name(int r) {
	switch (r) {
		case 1:  return "unreadable";		/* the file was found and could not be opened */
		case 2:  return "identification";	/* another version, serial, size or layout */
		case 3:  return "mode_list";		/* the file's modes are not the instrument's */
		case 4:  return "checksum";
		case 5:  return "read";				/* read; modes_restored / modes_skipped say which */
		default: return "no_file";			/* none found (or none looked for) */
	}
}

static int cq_wl_count_bits(int v) {
	int n = 0;
	for (; v != 0; v &= v - 1)
		n++;
	return n;
}

/* For an i1Pro 2: 0, and in *buf a JSON fragment (no braces):
 *   "source":"calibration"  a wavelength-LED calibration ran in this process
 *            "file"         mode 0's calibration was restored from the file,
 *                           and the filters were recomputed with it
 *            "factory"      neither: the EEPROM's factory filters
 *   "offset_nm"   the correction the filters use, nm (0 for factory), as
 *                 ArgyllCMS's own "Final WL offset ... correction %f nm"
 *   "offset_raw"  the same in raw sensor bins
 *   "restore"     what became of the calibration file (cq_wl_restore_name)
 *   "modes_restored" / "modes_skipped"   how many modes the file restored,
 *                 and how many it did not because their settings differ
 *   "age_s"       seconds since mode 0's wavelength calibration, -1 = none
 * Anything else (another instrument, no buffer): -1, *buf untouched. */
int i1pro2_cq_wl_report(void *pp, char *buf, int len) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	const char *src;
	double raw = 0.0, nm = 0.0;
	long age = -1;

	if (p == NULL || buf == NULL || len <= 0 || p->dtype != instI1Pro2 || p->m == NULL)
		return -1;
	m = (i1proimp *)p->m;
	if (i1pro_cq_wl_fresh)
		src = "calibration";
	else if (m->ms[0].wl_valid)
		src = "file";
	else
		src = "factory";
	if ((i1pro_cq_wl_fresh || m->ms[0].wl_valid) && i1pro_cq_wl_filters) {
		raw = i1pro_cq_wl_filters_off - m->wl_led_ref_off;
		nm = i1pro_raw2wav_uncal(p, i1pro_cq_wl_filters_off)
		   - i1pro_raw2wav_uncal(p, m->wl_led_ref_off);
	}
	if (m->ms[0].wl_valid && m->ms[0].wldate != 0)
		age = (long)(time(NULL) - m->ms[0].wldate);
	snprintf(buf, len, "\"source\":\"%s\",\"offset_nm\":%.3f,\"offset_raw\":%.3f,"
	         "\"restore\":\"%s\",\"modes_restored\":%d,\"modes_skipped\":%d,\"age_s\":%ld",
	         src, nm, raw, cq_wl_restore_name(i1pro_cq_wl_restore),
	         cq_wl_count_bits(i1pro_cq_wl_modes_ok), cq_wl_count_bits(i1pro_cq_wl_modes_skipped),
	         age);
	return 0;
}
