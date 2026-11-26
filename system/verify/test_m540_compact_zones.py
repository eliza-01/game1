"""Compact GP geometry contract; Studio test verifies actual CFrames."""
import json, math, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
class CompactZones(unittest.TestCase):
    def test_layout_and_status(self):
        s=(ROOT/'src/server/dev/GameplayTestLayout.luau').read_text()
        for token in ('local ZONE_SIZE = 384','local GAP = 24','local HEIGHT = 16','ZONE_SIZE/2-24','zoneSize=ZONE_SIZE','homeRadius=75','top.RightVector','point+facing*reach','Vector3.new(32,0,length+4)'):
            self.assertIn(token,s)
        self.assertIn('format(count, #rows, s.layout.zoneSize)',(ROOT/'src/server/dev/GameplayTestService.luau').read_text())
    def test_normal_points_and_visits_fit(self):
        data=json.loads((ROOT/'config/balance/gameplay.json').read_text())
        bands=((1,4),(5,9),(10,14),(15,19),(20,24),(25,30),(31,35))
        count=0
        for lo,hi in bands:
            points=[]
            for r in data['monsters']:
                if not lo<=r['level']<=hi: continue
                x=-108 if r['type']=='melee' else 108
                z=((hi-lo)/2-(r['level']-lo))*min(44,220/max(1,hi-lo))
                reach=max(30,r['attackRange']+12)
                v=x+reach if x<0 else x-reach
                self.assertLessEqual(max(abs(x),abs(z))+75,192)
                self.assertLess(max(abs(v),abs(z)),192)
                self.assertTrue(all(math.hypot(x-a,z-b)>=44 for a,b in points))
                points.append((x,z)); count+=1
        self.assertEqual(count,70)
    def test_skilled_and_entry(self):
        for i in range(8):
            x=(i%4-1.5)*72; z=(.5-i//4)*120
            self.assertLessEqual(max(abs(x),abs(z))+75,192)
            self.assertLess(max(abs(x),abs(z-52 if z>0 else z+52)),192)
        self.assertLess(384/2-24+3,192)
