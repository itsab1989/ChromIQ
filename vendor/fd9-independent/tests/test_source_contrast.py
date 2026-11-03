import unittest
from fd9_independent.spectral import Curve
from fd9_independent.source_contrast import fit_source_contrast


class SourceContrastTests(unittest.TestCase):
    def setUp(self):
        self.nm = (420, 430, 440, 450, 460)
        self.target = Curve(self.nm, (1, 1.1, 1.2, 1.3, 1.4))
        self.source = Curve(self.nm, (1, 2, 4, 2, 1))
        self.low = Curve(self.nm, (.3, .4, .5, .6, .7))
        self.emission = (.1, .2, .3, .2, .1)
        self.high = Curve(self.nm, [b + f/s for b, f, s in zip(self.low.values, self.emission, self.source.values)])
        self.reference = Curve(self.nm, [2*f/t for f, t in zip(self.emission, self.target.values)])

    def fit(self, source=None, reference=None, high=None):
        return fit_source_contrast(self.low, high or self.high, source or self.source, self.target, reference or self.reference, scope='synthetic experiment', reference_source='independent synthetic reference')

    def test_recovers_emission_when_source_has_a_blue_peak(self):
        model = self.fit()
        self.assertAlmostEqual(model.gain, 2)
        result = model.apply(self.low, self.high, self.source, self.target, scope=model.scope)
        self.assertFalse(result.validated)
        for actual, expected in zip(result.contrast.values, self.reference.values):
            self.assertAlmostEqual(actual, expected)

    def test_source_unit_scaling_is_compensated_by_fitted_gain(self):
        scaled = Curve(self.nm, [100*v for v in self.source.values])
        model = self.fit(source=scaled)
        self.assertAlmostEqual(model.gain, .02)
        result = model.apply(self.low, self.high, scaled, self.target, scope=model.scope)
        for actual, expected in zip(result.contrast.values, self.reference.values):
            self.assertAlmostEqual(actual, expected)

    def test_different_material_emission_is_not_a_new_coefficient_fit(self):
        model = self.fit()
        emission = (.03, .1, .05, .07, .01)
        high = Curve(self.nm, [b+f/s for b, f, s in zip(self.low.values, emission, self.source.values)])
        result = model.apply(self.low, high, self.source, self.target, scope=model.scope)
        for actual, f, t in zip(result.contrast.values, emission, self.target.values):
            self.assertAlmostEqual(actual, 2*f/t)

    def test_zero_contrast_and_negative_gain_fail(self):
        with self.assertRaisesRegex(ValueError, 'unidentifiable'):
            self.fit(high=self.low)
        with self.assertRaisesRegex(ValueError, 'positive finite research gain'):
            self.fit(reference=Curve(self.nm, [-v for v in self.reference.values]))

    def test_invalid_source_and_wrong_scope_fail(self):
        with self.assertRaisesRegex(ValueError, 'positive source'):
            self.fit(source=Curve(self.nm, (1, 2, 0, 2, 1)))
        model = self.fit()
        with self.assertRaisesRegex(ValueError, 'another experiment scope'):
            model.apply(self.low, self.high, self.source, self.target, scope='other capture')

    def test_negative_holdout_contrast_is_not_clipped(self):
        model = self.fit()
        high = Curve(self.nm, [v-.01 for v in self.low.values])
        result = model.apply(self.low, high, self.source, self.target, scope=model.scope)
        self.assertTrue(all(v < 0 for v in result.contrast.values))

    def test_missing_wavelength_coverage_fails(self):
        with self.assertRaises(ValueError):
            self.fit(source=Curve((430, 440, 450), (2, 4, 2)))


if __name__ == '__main__':
    unittest.main()
