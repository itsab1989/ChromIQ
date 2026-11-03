import unittest
from fd9_independent.spectral import Curve,product_integral,colorimetry,xyz_to_lab
from fd9_independent.fluorescence import combine

class SpectralTests(unittest.TestCase):
    def test_linear_interpolation_and_no_extrapolation(self):
        c=Curve([400,500,700],[.2,.6,.4]);self.assertAlmostEqual(c.at(450),.4);self.assertAlmostEqual(c.at(600),.5)
        self.assertEqual(c.resample((400,700)).values,(.2,.4))
        self.assertEqual(c.resample(w for w in (400,700)).values,(.2,.4))
        for w in (399,701,float('nan')):
            with self.assertRaises(ValueError):c.at(w)
        for w,v in [([400,400],[1,2]),([400,500],[1,float('nan')]),([400],[1])]:
            with self.assertRaises(ValueError):Curve(w,v)
    def test_piecewise_product_integral_exact_on_different_knots(self):
        a=Curve([0,1],[0,1]);b=Curve([0,.25,1],[0,.25,1]);c=Curve([0,.75,1],[0,.75,1])
        self.assertAlmostEqual(product_integral((a,b),0,1),1/3)
        self.assertAlmostEqual(product_integral((a,b,c),0,1),1/4)
        with self.assertRaises(ValueError):product_integral((a,),-1,1)
    def test_white_black_and_neutral_colorimetry(self):
        illuminant=Curve([400,700],[1,1]);observer=(Curve([400,700],[1,2]),Curve([400,700],[2,2]),Curve([400,700],[2,1]))
        white=colorimetry(Curve([400,700],[1,1]),illuminant,observer);self.assertAlmostEqual(white.xyz[1],100);self.assertEqual(white.lab,(100,0,0));self.assertEqual(white.coverage_nm,(400,700))
        black=colorimetry(Curve([400,700],[0,0]),illuminant,observer);self.assertEqual(black.lab,(0,0,0))
        neutral=colorimetry(Curve([400,700],[.5,.5]),illuminant,observer);self.assertAlmostEqual(neutral.lab[0],76.06926101415557);self.assertAlmostEqual(neutral.lab[1],0)
        with self.assertRaises(ValueError):colorimetry(Curve([380,730],[.5,.5]),illuminant,observer)
    def test_lab_linear_branch_and_negative_measurement_not_clipped(self):
        self.assertAlmostEqual(xyz_to_lab((.1,.1,.1),(100,100,100))[0],24389/27*.001)
        self.assertLess(xyz_to_lab((-1,-1,-1),(100,100,100))[0],0)
    def sources(self):
        # Explicit invented ultraviolet and visible spectra; no instrument data.
        grid=[300,350,400,500,700]
        one=Curve(grid,[1,1,1,1,1]);two=Curve(grid,[3,3,1,1,1]);target=Curve(grid,[2,2,1,1,1]);excitation=Curve([300,350],[1,1])
        return one,two,target,excitation
    def test_two_illuminant_model_recovers_synthetic_fluorescence(self):
        one,two,target,e=self.sources();a=Curve([500,700],[.5,.3]);b=Curve([500,700],[.9,.5])
        r=combine(a,b,one,two,target,e,[500,700]);self.assertAlmostEqual(r.radiance_factor.values[0],.7);self.assertAlmostEqual(r.radiance_factor.values[1],.4);self.assertEqual(r.weights,(.5,.5));self.assertFalse(r.validated)
        self.assertEqual(combine(a,b,one,two,one,e,[500,700]).radiance_factor.values,a.values)
    def test_scale_invariance_and_no_hidden_extrapolation_clamp(self):
        one,two,target,e=self.sources();a=Curve([500,700],[.5,.3]);b=Curve([500,700],[.9,.5])
        scaled=Curve(two.wavelengths,[v*123 for v in two.values]);r=combine(a,b,one,scaled,target,e,[500,700]);self.assertAlmostEqual(r.radiance_factor.values[0],.7)
        strong=Curve(one.wavelengths,[5,5,1,1,1]);r=combine(a,b,one,two,strong,e,[500,700]);self.assertAlmostEqual(r.weights[0],-1);self.assertAlmostEqual(r.radiance_factor.values[0],1.3)
    def test_unknown_or_missing_excitation_fails_closed(self):
        one,two,target,e=self.sources();a=Curve([500,700],[.5,.3])
        with self.assertRaises(ValueError):combine(a,a,one,one,target,e,[500,700])
        with self.assertRaises(ValueError):combine(a,a,one,two,target,Curve([280,350],[1,1]),[500,700])
        with self.assertRaises(ValueError):combine(a,a,one,two,target,Curve([300,350],[0,0]),[500,700])
        negative=Curve(one.wavelengths,[-1,1,1,1,1])
        with self.assertRaises(ValueError):combine(a,a,negative,two,target,e,[500,700])

if __name__=='__main__':unittest.main()
