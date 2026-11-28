"""M572: execute the shared collision matrix policy without Roblox physics."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class NonPlayerCollision(unittest.TestCase):
    def test_actual_policy_matrix_and_phantom(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        source = (ROOT / 'src/server/actor/ActorCollisionPolicy.luau').read_text()
        source = source.replace('root: BasePart, kind: "Character" | "Monster" | "NPC"', 'root, kind')
        source = source.replace('actor: Model', 'actor')
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / 'policy.lua'
            policy.write_text(source)
            test = Path(directory) / 'test.lua'
            test.write_text('''
local registered = {Default=true}
local matrix, count = {}, 0
local function key(a,b) if a>b then a,b=b,a end; return a..":"..b end
local physics = {}
function physics:IsCollisionGroupRegistered(g) return registered[g] == true end
function physics:RegisterCollisionGroup(g) assert(not registered[g]); registered[g]=true end
function physics:CollisionGroupSetCollidable(a,b,value)
    assert(registered[a] and registered[b]); matrix[key(a,b)]=value; count=count+1
end
function physics:CollisionGroupsAreCollidable(a,b) return matrix[key(a,b)] end
game={GetService=function(_,name) assert(name=="PhysicsService"); return physics end}
table.freeze=function(t) return t end
local P=assert(loadfile(arg[1]))()
local function root(kind)
    local r={CanCollide=false,CanQuery=true,CanTouch=true}
    P.Assign(r,kind)
    assert(r.CanCollide and r.CanQuery and r.CanTouch)
    return r
end
local monster, npc, player = root("Monster"), root("NPC"), root("Character")
local function collides(a,b) return physics:CollisionGroupsAreCollidable(a.CollisionGroup,b.CollisionGroup) end
assert(not collides(monster,npc) and not collides(monster,monster) and not collides(npc,npc))
assert(collides(player,npc) and collides(player,monster) and collides(player,player))
for _,r in ipairs({monster,npc,player}) do assert(physics:CollisionGroupsAreCollidable(r.CollisionGroup,"Default")) end
assert(count==5, "initialize matrix only once")
local respawn=root("Monster"); assert(respawn.CollisionGroup==monster.CollisionGroup and count==5)
local hitbox={CanCollide=false,CanQuery=true,CanTouch=true}
for _,r in ipairs({monster,hitbox}) do r.IsA=function(_,kind) return kind=="BasePart" end end
P.MakePhantom({GetDescendants=function() return {monster,hitbox} end})
assert(not monster.CanCollide and not monster.CanQuery and not monster.CanTouch)
assert(not hitbox.CanCollide and not hitbox.CanQuery and not hitbox.CanTouch)
assert(npc.CanCollide and respawn.CanCollide and player.CanCollide)
''')
            result = subprocess.run([lua, str(test), str(policy)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_navigation_uses_physical_group_without_changing_combat_hitboxes(self):
        for file in ('MonsterRecoveryGeometry', 'MonsterRangedRetreat'):
            source = (ROOT / f'src/server/monster/{file}.luau').read_text()
            self.assertRegex(source, r'CollisionGroup\s*=\s*agent\.root\.CollisionGroup')
        for files in (('src/server/actor/MnpcNavigationShell.luau', 'src/server/actor/MnpcVisualRig.luau'),):
            source = '\n'.join((ROOT / file).read_text() for file in files)
            self.assertIn('CanCollide = false', source)
            self.assertIn('CanQuery = true', source)
