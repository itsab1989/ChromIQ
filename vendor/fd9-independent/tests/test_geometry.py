import unittest
from fd9_independent.geometry import find_marks,grid_rows

class GeometryTests(unittest.TestCase):
    def image(self,marks):
        w,h=500,800;p=bytearray(b'\xff'*(w*h))
        for cx,cy in marks:
            for y in range(cy-20,cy+20):p[y*w+cx-20:y*w+cx+20]=b'\0'*40
        # Larger patch block must not be mistaken for a fiducial.
        for y in range(350,450):p[y*w+180:y*w+280]=b'\0'*100
        return bytes(p),w,h
    def test_translated_and_skewed_grid(self):
        expected=[(90,100),(390,104),(84,690),(384,694)]
        marks=find_marks(*self.image(expected))
        for actual,target in zip(marks,expected):
            for a,b in zip(actual,target):self.assertAlmostEqual(a,b-.5)
        rows=grid_rows(marks,list(range(19,119,9)),[42,123,258])
        self.assertEqual([len(r) for r in rows],[12,12,12]);self.assertLess(rows[0][0][1],rows[2][0][1]);self.assertLess(rows[1][0][1],rows[1][-1][1])
    def test_missing_or_ambiguous_marks_reject(self):
        for marks in [[(90,100),(390,100),(90,690)],[(90,100),(390,100),(90,690),(390,690),(90,400)]]:
            with self.assertRaises(ValueError):find_marks(*self.image(marks))
    def test_bad_grid_rejects(self):
        m=[(90,100),(390,100),(90,690),(390,690)]
        for x,y in [(list(range(19,119,9)),[123,42]),(list(range(19,119,9)),[300]),([19]*12,[42])]:
            with self.assertRaises(ValueError):grid_rows(m,x,y)
    def test_mirrored_off_centre_asymmetric_positions(self):
        # Reflection must include the whole image, not the fiducial rectangle's
        # centre. Y follows the physical point on a skewed mirrored image.
        m=[(100,100),(400,106),(90,700),(390,706)]
        xs=[10+i for i in range(12)]
        row=grid_rows(m,xs,[50],mark_span_mm=(100,100),mark_origin_mm=(0,0),mirrored_image=True,image_width_px=600)[0]
        self.assertAlmostEqual(row[0][0],235)
        self.assertAlmostEqual(row[0][1],405.4)
        self.assertLess(row[0][0],row[-1][0])
        self.assertGreater(row[0][1],row[-1][1])
    def test_mirrored_mapping_requires_valid_width(self):
        m=[(100,100),(400,100),(100,700),(400,700)]
        for width in (None,True,300,600.5):
            with self.assertRaises(ValueError):grid_rows(m,list(range(19,119,9)),[42],mirrored_image=True,image_width_px=width)
