import math
import unittest
from fd9_independent.spectral import Curve
from fd9_independent.m2_research import FIT_BANDS, OUTPUT_BANDS, M2ResearchModel, fit_m2_research


class M2ResearchTests(unittest.TestCase):
    def setUp(self):
        self.weights = tuple(-.2 + i*.01 for i in range(len(FIT_BANDS)))
        self.model = M2ResearchModel(self.weights, 'unit/calibration/1', 'synthetic')

    def curves(self, offset, contrast):
        low = Curve(OUTPUT_BANDS, tuple(offset + i*.001 for i in range(36)))
        high = Curve(OUTPUT_BANDS, tuple(v + contrast*(1+i*.02) for i, v in enumerate(low.values)))
        return low, high

    def test_recovers_known_weights_and_unseen_spectrum(self):
        refs = []
        for a, d in ((.3, .07), (.6, .02), (.8, .13)):
            low, high = self.curves(a, d)
            ref = self.model.apply(low, high, scope=self.model.scope).spectrum
            refs.append((low, high, ref))
        fit = fit_m2_research(refs, scope=self.model.scope, reference_source='synthetic')
        for got, expected in zip(fit.high_source_weights, self.weights):
            self.assertAlmostEqual(got, expected, places=12)
        low, high = self.curves(.04, .19)
        got = fit.apply(low, high, scope=fit.scope)
        expected = self.model.apply(low, high, scope=self.model.scope)
        for a, b in zip(got.spectrum.values, expected.spectrum.values):
            self.assertAlmostEqual(a, b, places=12)
        self.assertFalse(got.calibrated)

    def test_reporting_edges_and_red_average(self):
        low, high = self.curves(.3, .05)
        result = self.model.apply(low, high, scope=self.model.scope).spectrum
        self.assertEqual(result.at(380), result.at(400))
        self.assertEqual(result.at(390), result.at(400))
        for w in range(620, 721, 10):
            self.assertEqual(result.at(w), (low.at(w)+high.at(w))/2)
        self.assertAlmostEqual(result.at(730), 2*result.at(720)-result.at(710))

    def test_negative_values_and_nonconvex_weights_retained(self):
        low, high = self.curves(.001, .1)
        self.assertLess(self.model.apply(low, high, scope=self.model.scope).spectrum.at(430), 0)

    def test_scope_and_coverage_fail_closed(self):
        low, high = self.curves(.3, .05)
        with self.assertRaises(ValueError): self.model.apply(low, high, scope='other unit')
        truncated = Curve((400, 610), (.3, .4))
        with self.assertRaises(ValueError): self.model.apply(truncated, high, scope=self.model.scope)

    def test_unidentifiable_and_insufficient_references(self):
        low, high = self.curves(.3, .05)
        with self.assertRaises(ValueError): fit_m2_research([(low, high, low)], scope='a', reference_source='b')
        for high in (low, Curve(OUTPUT_BANDS, tuple(v+1e-9 for v in low.values))):
            with self.assertRaises(ValueError):
                fit_m2_research([(low, high, low)]*2, scope='a', reference_source='b')

    def test_invalid_model_and_threshold(self):
        for weights in ((), (math.nan,)*22):
            with self.assertRaises(ValueError): M2ResearchModel(weights, 'a', 'b')
        with self.assertRaises(ValueError): M2ResearchModel(self.weights, '', 'b')
        low, high = self.curves(.3, .05)
        for threshold in (0, math.nan):
            with self.assertRaises(ValueError):
                fit_m2_research([(low, high, low)]*2, scope='a', reference_source='b', minimum_rms_contrast=threshold)


if __name__ == '__main__': unittest.main()
