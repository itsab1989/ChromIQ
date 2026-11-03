import unittest
from fd9_independent.reference import read_cgats

class ReferenceTests(unittest.TestCase):
    def source(self,extra='',fields='SAMPLE_ID SPEC_380 SPEC_730',rows='"paper white" 90 80',sets=1):
        return f'CGATS.17\nNUMBER_OF_FIELDS 3\nNUMBER_OF_SETS {sets}\n{extra}\nBEGIN_DATA_FORMAT\n{fields}\nEND_DATA_FORMAT\nBEGIN_DATA\n{rows}\nEND_DATA\n'
    def test_percent_normalization_and_quoted_identifier(self):
        m,s=read_cgats(self.source('SPECTRAL_NORM 100'));self.assertEqual(s[0].sample_id,'paper white');self.assertEqual(s[0].curve.values,(.9,.8))
    def test_missing_or_conflicting_scale_is_rejected(self):
        with self.assertRaises(ValueError):read_cgats(self.source())
        with self.assertRaises(ValueError):read_cgats(self.source('SPECTRAL_NORM 100'),normalization=1)
        m,s=read_cgats(self.source(fields='SAMPLE_ID nm380 nm730',rows='a .9 .8'),normalization=1);self.assertEqual(s[0].curve.values,(.9,.8))
    def test_implicit_row_identifier_for_spotread_spectrum(self):
        t=self.source('SPECTRAL_NORM 100\nSPECTRAL_BANDS 2\nSPECTRAL_START_NM 380\nSPECTRAL_END_NM 730',fields='SPEC_380 SPEC_730',rows='90 80').replace('NUMBER_OF_FIELDS 3','NUMBER_OF_FIELDS 2')
        m,s=read_cgats(t);self.assertEqual(s[0].sample_id,'1')
    def test_bad_spectra_counts_and_duplicates_reject(self):
        cases=[self.source('SPECTRAL_NORM 100',rows='a nan 80'),self.source('SPECTRAL_NORM 100',sets=2),self.source('SPECTRAL_NORM 100',fields='SAMPLE_ID SPEC_380 SPEC_380'),self.source('SPECTRAL_NORM 100',rows='a 90 80\na 80 70',sets=2),self.source('SPECTRAL_NORM 100\nSPECTRAL_BANDS 3')]
        for text in cases:
            with self.assertRaises(ValueError):read_cgats(text)
