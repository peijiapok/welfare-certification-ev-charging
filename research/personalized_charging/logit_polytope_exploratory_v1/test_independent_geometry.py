"""Independent exact geometric controls; no stored scientific data are read."""
from fractions import Fraction as F
import unittest
from personalized_charging.logit_polytope_exploratory_v1.projector import vertices, project_bands

# Coordinates are lambda, v; each row encodes a*lambda+b*v <= c.
PRIOR=((F(-1),F(0),F(-5,2)), (F(1),F(0),F(20)),
       (F(0),F(-1),F(0)), (F(-1,4),F(1),F(0)))

def extrema(rows):
    pts=vertices(rows)
    return pts, (min(v/l for l,v in pts),max(v/l for l,v in pts)) if pts else None

class IndependentGeometry(unittest.TestCase):
    def test_full_prior_polygon_with_unobserved_streams(self):
        pts,bounds=extrema(PRIOR)
        self.assertEqual(set(pts),{(F(5,2),F(0)),(F(5,2),F(5,8)),(F(20),F(0)),(F(20),F(5))})
        self.assertEqual(bounds,(F(0),F(1,4)))
        result=project_bands({'p':['0','1'],'r':['0','1'],'third':['0','1']},method='three')
        self.assertEqual(result['status'],'PROJECTED',result)
        self.assertEqual(list(map(F,result['theta_bounds_exact_outer'])),[F(0),F(1,4)])

    def test_degenerate_segment_and_point(self):
        # v=1/2 and lambda<=4: theta ranges exactly from 1/8 to 1/5.
        segment=PRIOR+((F(0),F(1),F(1,2)),(F(0),F(-1),F(-1,2)),(F(1),F(0),F(4)))
        pts,bounds=extrema(segment)
        self.assertEqual(set(pts),{(F(5,2),F(1,2)),(F(4),F(1,2))})
        self.assertEqual(bounds,(F(1,8),F(1,5)))
        # Lambda=4 and v=1 leaves only the prior's upper-theta boundary.
        point=PRIOR+((F(1),F(0),F(4)),(F(-1),F(0),F(-4)),
                     (F(0),F(1),F(1)),(F(0),F(-1),F(-1)))
        pts,bounds=extrema(point)
        self.assertEqual(pts,((F(4),F(1)),))
        self.assertEqual(bounds,(F(1,4),F(1,4)))
        # A lower dimensional edge has constant theta, despite a loose box.
        edge=PRIOR+((F(1,4),F(-1),F(0)),)
        pts,bounds=extrema(edge)
        self.assertEqual(bounds,(F(1,4),F(1,4)))

    def test_contradictory_and_unbounded_intercept_cases(self):
        empty=PRIOR+((F(1),F(0),F(3)),(F(-1),F(0),F(-4)))
        self.assertEqual(vertices(empty),())
        one_sided={'p':['0','.4'],'r':['0','.4'],'third':['0','.4']}
        result=project_bands(one_sided,method='three')
        self.assertEqual(result['status'],'PROJECTED',result)
        self.assertEqual(list(map(F,result['theta_bounds_exact_outer'])),[F(0),F(1,4)])
        contradictory=project_bands({'p':['.8','.9'],'r':['.1','.2']},method='two')
        self.assertEqual(contradictory['status'],'ABSTAIN')
        self.assertEqual(contradictory['reason'],'empty_outer')
        for invalid in (['0','0'],['1','1'],['.8','.1'],['-1','.5'],['NaN','.5']):
            self.assertEqual(project_bands({'p':invalid,'r':['0','1']},method='two')['status'],'ABSTAIN')

if __name__=='__main__': unittest.main()
