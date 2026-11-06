import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bathymetry

class BathymetryTests(unittest.TestCase):
    def test_parse_preserves_negative_depth_and_nulls(self):
        raw=b'''Dataset {}\n---------------------------------------------\nelevation.elevation[2][2]\n[0], -100, -200\n[1], 10, -32768\n\nelevation.lat[2]\n34, 35\n\nelevation.lon[2]\n139, 140\n'''
        grid=bathymetry.parse(raw)
        self.assertEqual(grid['height_m'],[-100,-200,10,None])
        self.assertEqual(grid['vertical_datum'],'Mean Sea Level (some shallow-water sources differ)')
        self.assertTrue(grid['not_for_navigation'])
        with self.assertRaises(ValueError):bathymetry.parse(raw.replace(b'[0], -100, -200',b'[0], -100'))

    def test_fixed_subset_limits_and_polar_coordinates(self):
        self.assertEqual(bathymetry.index(-90,90,43200),0)
        self.assertEqual(bathymetry.index(90,90,43200),43199)
        self.assertIn('[0:480:43199]',bathymetry.url('bathymetry-base'))
        self.assertIn('.ascii?elevation[',bathymetry.url('bathymetry',{'lat':35,'lon':139}))
