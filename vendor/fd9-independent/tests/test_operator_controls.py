from pathlib import Path
import tempfile,unittest
from fd9_independent.operator_controls import fresh_output,stage_control


class OperatorControlTests(unittest.TestCase):
    def test_retries_preserve_previous_attempts(self):
        with tempfile.TemporaryDirectory() as t:
            original=fresh_output(Path(t)/'session');(original/'progress.json').write_text('preserved')
            first=fresh_output(original);second=fresh_output(original)
            self.assertNotEqual(first,second);self.assertNotEqual(original,first)
            self.assertEqual((original/'progress.json').read_text(),'preserved')
            self.assertTrue(first.is_dir());self.assertTrue(second.is_dir())

    def test_out_of_order_input_does_not_advance_a_stage(self):
        self.assertFalse(stage_control('scan','load'));self.assertFalse(stage_control('','load'))
        self.assertTrue(stage_control(' LOAD ','load'));self.assertFalse(stage_control('load','scan'))
        self.assertTrue(stage_control('scan','scan'))
        with self.assertRaises(RuntimeError):stage_control('abort','load')
