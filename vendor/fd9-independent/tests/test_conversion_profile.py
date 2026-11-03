import hashlib,json,tempfile,unittest
from pathlib import Path
from fd9_independent.conversion_profile import ConversionProfile


class ConversionProfileTests(unittest.TestCase):
    def document(self):
        return {'schema':1,'calibrated':False,'host':'test-host','calibration_sha256':hashlib.sha256(b'test-cal').hexdigest(),
                'conditions':{m:{'high_source_weights':[.2]*22,'reference_source':'synthetic'} for m in ('M1','M2')}}
    def load(self,document):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'profile.json';p.write_text(json.dumps(document));return ConversionProfile.load(p)
    def test_mode_edges_and_identity(self):
        p=self.load(self.document());b=[[.3]*38,[.8]*38,[1.]*38,[1.]*38]
        a=p.convert(b,'M1',host='test-host',calibration=b'test-cal',allow_research=True)
        c=p.convert(b,'M2',host='test-host',calibration=b'test-cal',allow_research=True)
        self.assertEqual(a.spectrum.at(380),.8)
        self.assertAlmostEqual(c.spectrum.at(380),.4)
        self.assertFalse(a.calibrated)
        for host,cal in [('other',b'test-cal'),('test-host',b'changed')]:
            with self.assertRaises(ValueError):p.convert(b,'M1',host=host,calibration=cal,allow_research=True)
        with self.assertRaises(ValueError):p.convert(b,'M1',host='test-host',calibration=b'test-cal')
        with self.assertRaises(ValueError):p.convert(b,'M0',host='test-host',calibration=b'test-cal',allow_research=True)
        b[2][0]=float('nan')
        with self.assertRaises(ValueError):p.convert(b,'M1',host='test-host',calibration=b'test-cal',allow_research=True)
    def test_invalid_profiles_fail_before_conversion(self):
        for key,value in [('calibrated',True),('schema',True),('host',''),('calibration_sha256','not-a-digest'),('conditions',{})]:
            p=self.document();p[key]=value
            with self.assertRaises(ValueError):self.load(p)
        p=self.document();p['conditions']['M1']['high_source_weights']=[]
        with self.assertRaises(ValueError):self.load(p)

    def test_optional_m0_requires_its_own_external_calibration(self):
        doc=self.document();doc['conditions']['M0']={'high_source_weights':[.8]*22,'reference_source':'synthetic explicit M0'}
        p=self.load(doc);blocks=[[.2]*38,[.7]*38,[1.]*38,[1.]*38]
        result=p.convert(blocks,'M0',host='test-host',calibration=b'test-cal',allow_research=True)
        self.assertEqual(result.spectrum.at(380),.7)
        self.assertAlmostEqual(result.spectrum.at(500),.6)
        self.assertAlmostEqual(result.spectrum.at(700),.45)
        self.assertIn('M0',result.description);self.assertFalse(result.calibrated)
        blocks[0]=[-.5]*38;blocks[1]=[-.2]*38
        result=p.convert(blocks,'M0',host='test-host',calibration=b'test-cal',allow_research=True)
        self.assertTrue(all(v==.0001 for v in result.spectrum.values))
        doc['conditions']['unknown']=doc['conditions']['M0']
        with self.assertRaises(ValueError):self.load(doc)


    def test_m0_source_adjustment_is_scoped_and_returns_m0(self):
        doc=self.document();doc['conditions']['M0']={'high_source_weights':[.2]*22,'reference_source':'synthetic source response',
            'reference_sources':[1.]*76,'source_jacobian':[[.01]*76 for _ in range(22)],'allowed_source_delta':[.1]*76}
        p=self.load(doc);b=[[.2]*38,[.7]*38,[1.]*38,[1.]*38];b[2][0]=1.05
        result=p.convert(b,'M0',host='test-host',calibration=b'test-cal',allow_research=True)
        self.assertAlmostEqual(result.spectrum.at(500),.2+.2005*.5)
        self.assertIn('M0',result.description)
        b[2][0]=2.
        with self.assertRaises(ValueError):p.convert(b,'M0',host='test-host',calibration=b'test-cal',allow_research=True)
