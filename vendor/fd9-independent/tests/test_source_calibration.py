import unittest
from fd9_independent.source_calibration import SourceAdjustedM1


class SourceCalibrationTests(unittest.TestCase):
    def model(self):
        jac=[[0.]*76 for _ in range(22)];jac[0][3]=2.;jac[1][40]=-.5
        return SourceAdjustedM1([.2]*22,'scope','synthetic',[1.]*76,jac,[.1]*76)
    def test_source_response_and_domain(self):
        m=self.model();b=[[.3]*38,[.8]*38,[1.]*38,[1.]*38]
        b[2][3]+=.04;b[3][2]+=.06
        r=m.apply_raw(b,scope='scope')
        self.assertAlmostEqual(r.spectrum.at(400),.3+(.2+.08)*.5)
        self.assertAlmostEqual(r.spectrum.at(410),.3+(.2-.03)*.5)
        self.assertEqual(r.spectrum.at(380),.8)
        self.assertFalse(r.calibrated)
        with self.assertRaises(ValueError):m.apply_raw(b,scope='another')
        b[2][0]=1.11
        with self.assertRaises(ValueError):m.apply_raw(b,scope='scope')
    def test_invalid_calibration_and_raw_input(self):
        m=self.model()
        with self.assertRaises(ValueError):SourceAdjustedM1(m.high_source_weights,'s','r',[1.],m.source_jacobian,m.allowed_source_delta)
        with self.assertRaises(ValueError):SourceAdjustedM1(m.high_source_weights,'s','r',m.reference_sources,m.source_jacobian,[0.]*76)
        with self.assertRaises(ValueError):m.apply_raw([[.3]*38]*3,scope='scope')
