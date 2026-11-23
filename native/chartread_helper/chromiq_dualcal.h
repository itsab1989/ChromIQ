/* chromiq_dualcal.h: the start-up calibration an i1Pro 2 dual session asks
 * ArgyllCMS for (ChromIQ 4.3.58, item 40). Needs inst.h first.
 *
 * Everything a NORMAL session asks for at this point (inst_calt_needed: at
 * the first calibration of a session that is the LED wavelength
 * calibration, the dark and the white, i1pro_imp.c:1626-1640), and the white
 * in any case: the dual scan reads the tile with the UV LED at the white's
 * own exposure right after it (cq_dd_after_cal), and a white restored from
 * ArgyllCMS's file has no such reading. The driver does them in its own
 * fixed order (wavelength, dark, white: i1pro_imp_calibrate), so the wire is
 * a normal session's start-up calibration followed by the dual tile.
 *
 * 4.3.48 to 4.3.57 asked for inst_calt_ref_white alone: ArgyllCMS then
 * skipped the wavelength calibration (i1pro_imp.c:1768-1771) and the dark
 * before the white, and every dual-scan reading (M0, M1, M2) carried the
 * factory or a stale wavelength offset, about 1 nm (item 40).
 * AGPL-3.0 like the rest of the helper (see ../instlib/License.txt). */

#ifndef CHROMIQ_DUALCAL_H
#define CHROMIQ_DUALCAL_H

static inst_cal_type cq_dual_startup_calt(inst_cal_type needed) {
	return (inst_cal_type)((needed & inst_calt_n_dfrble_mask) | inst_calt_ref_white);
}

#endif /* CHROMIQ_DUALCAL_H */
