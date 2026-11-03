import unittest
from fd9_independent.spectral import Curve
from fd9_independent.reference_blend import fit_reference_blend

class ReferenceBlendTests(unittest.TestCase):
    def test_known_blend_recovers_held_out_sample(self):
        a=Curve((400,700),(.8,.4));b=Curve((400,700),(.4,.8));r=Curve((400,700),(.5,.5))
        m=fit_reference_blend(a,b,r,(1e-6,1e-6),scope='sheet/run',reference_source='independent instrument')
        self.assertAlmostEqual(m.weights[0],.25);self.assertAlmostEqual(m.weights[1],.75);self.assertEqual(m.identified,(True,True))
        result=m.apply(Curve((400,700),(.6,.3)),Curve((400,700),(.2,.7)),scope='sheet/run')
        self.assertAlmostEqual(result.radiance_factor.values[0],.3);self.assertAlmostEqual(result.radiance_factor.values[1],.4);self.assertFalse(result.validated)
    def test_unidentifiable_sources_are_marked_and_scope_cannot_transfer(self):
        c=Curve((400,700),(.5,.5));m=fit_reference_blend(c,c,c,(.01,.01),scope='run1',reference_source='reference')
        self.assertEqual(m.identified,(False,False));self.assertEqual(m.weights,(.5,.5))
        with self.assertRaises(ValueError):m.apply(c,c,scope='run2')
    def test_extrapolating_weights_are_preserved(self):
        m=fit_reference_blend(Curve((400,700),(.8,.8)),Curve((400,700),(.4,.4)),Curve((400,700),(1,1)),(1e-6,1e-6),scope='run',reference_source='reference')
        self.assertGreater(m.weights[0],1)
    def test_uncertainty_and_provenance_required(self):
        c=Curve((400,700),(.5,.5))
        for sigma in ((0,.01),(.01,),(.01,float('nan'))):
            with self.assertRaises(ValueError):fit_reference_blend(c,c,c,sigma,scope='run',reference_source='reference')
        with self.assertRaises(ValueError):fit_reference_blend(c,c,c,(.01,.01),scope='',reference_source='reference')

    def test_small_uncertainty_is_stable_and_overflow_fails(self):
        c=Curve((400,700),(.5,.5));m=fit_reference_blend(c,c,c,(1e-300,1e-300),scope='run',reference_source='ref')
        self.assertEqual(m.weights,(.5,.5))
        with self.assertRaises(ValueError):fit_reference_blend(Curve((400,700),(1e308,1e308)),Curve((400,700),(-1e308,-1e308)),c,(.01,.01),scope='run',reference_source='ref')
