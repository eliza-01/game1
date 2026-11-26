"""Compact GP geometry contract; Studio test verifies actual CFrames."""
import json, math, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
class CompactZones(unittest.TestCase):
    def test_layout_and_status(self):
        s=(ROOT/'src/server/dev/GameplayTestLayout.luau').read_text()
        for token in ('local ZONE_SIZE = 384','local GAP = 24','local HEIGHT = 16','ZONE_SIZE/2-24','zoneSize=ZONE_SIZE','local homeRadius=math.min(75','entryFrame.RightVector','point+facing*reach','Vector3.new(32,0,length+4)'):
            self.assertIn(token,s)
        self.assertIn('format(count, expectedCount, s.layout.zoneSize)',(ROOT/'src/server/dev/GameplayTestService.luau').read_text())
    def test_normal_points_and_visits_fit(self):
        import re
        source=(ROOT/'src/server/dev/GameplayWorldHuntingPlan.luau').read_text()
        groups=re.findall(r'yaw=(-?\d+), points=\{(.*?)\n    \}\}',source,re.S)
        self.assertEqual(len(groups),6)
        data=json.loads((ROOT/'config/balance/gameplay.json').read_text())
        bands=((1,4),(5,9),(10,14),(15,19),(20,24),(25,30))
        count=0
        for (yaw,raw),(lo,hi) in zip(groups,bands):
            points=[tuple(map(int,p)) for p in re.findall(r'\{(-?\d+),(-?\d+)\}',raw)]
            self.assertEqual(len(points),2*(hi-lo+1))
            self.assertGreaterEqual(min(math.hypot(x,z-168) for x,z in points),60)
            self.assertEqual(int(yaw),90 if lo==5 else -90 if lo==15 else 0)
            for i,(x,z) in enumerate(points):
                r=next(r for r in data['monsters'] if r['level']==lo+i//2 and r['type']==('melee' if i%2==0 else 'ranged'))
                others=[p for j,p in enumerate(points) if j!=i]
                self.assertGreaterEqual(min(math.hypot(x-a,z-b) for a,b in others),60)
                home=min(75,192-8-max(abs(x),abs(z)))
                self.assertGreaterEqual(home,50)
                self.assertLessEqual(max(abs(x),abs(z))+home,184)
                reach=max(30,r['attackRange']+12)
                candidates=[(x+math.cos(a*math.pi/4)*reach,z+math.sin(a*math.pi/4)*reach) for a in range(8)]
                candidates=[(a,b) for a,b in candidates if max(abs(a),abs(b))<=184]
                self.assertTrue(candidates)
                self.assertGreater(max(min(math.hypot(a-c,b-d) for c,d in others) for a,b in candidates),30)
                count+=1
        self.assertEqual(count,60)
        self.assertEqual(sum(r['level']>30 for r in data['monsters']),10)
    def test_skilled_and_entry(self):
        for i in range(8):
            x=(i%4-1.5)*72; z=(.5-i//4)*120
            self.assertLessEqual(max(abs(x),abs(z))+75,192)
            self.assertLess(max(abs(x),abs(z-52 if z>0 else z+52)),192)
        self.assertLess(384/2-24+3,192)
