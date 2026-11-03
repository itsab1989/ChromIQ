import unittest
from fd9_independent.m1_research import M1ResearchModel, fit_m1_research
from fd9_independent.m2_research import OUTPUT_BANDS
from fd9_independent.spectral import Curve


class M1ResearchTests(unittest.TestCase):
    def test_fit_and_unseen_fluorescent_holdout(self):
        weights = tuple(.1+i*.15 for i in range(22))
        model = M1ResearchModel(weights, 'unit/session', 'synthetic')
        def pair(a,d):
            low=Curve(OUTPUT_BANDS,[a+i*.001 for i in range(36)])
            high=Curve(OUTPUT_BANDS,[v+d*(1+i*.01) for i,v in enumerate(low.values)])
            return low,high
        refs=[]
        for a,d in ((.2,.04),(.6,.11)):
            low,high=pair(a,d)
            refs.append((low,high,model.apply(low,high,scope=model.scope).spectrum))
        fit=fit_m1_research(refs,scope=model.scope,reference_source='synthetic')
        low,high=pair(.05,.19)
        got=fit.apply(low,high,scope=fit.scope)
        expected=model.apply(low,high,scope=model.scope)
        for a,b in zip(got.spectrum.values,expected.spectrum.values):self.assertAlmostEqual(a,b,places=12)
        self.assertEqual(got.spectrum.at(380),high.at(380))
        self.assertEqual(got.spectrum.at(390),high.at(390))
        self.assertFalse(got.calibrated)
        with self.assertRaises(ValueError):fit.apply(low,high,scope='different')
