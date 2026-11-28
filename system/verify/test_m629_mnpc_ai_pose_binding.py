"""M629 common readiness contract and separate native pose attachment.
Lua checks execute actual binding/intent code; engine movement remains NOT_RUN.
"""
from pathlib import Path
import shutil, subprocess, tempfile, unittest, hashlib, json
ROOT = Path(__file__).resolve().parents[2]
def read(path): return (ROOT/path).read_text(encoding='utf-8')

class MnpcAiPoseBinding(unittest.TestCase):
    def test_ticket_and_motion_intent_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            files=[]
            for file in ('src/server/actor/MnpcPoseBinding.luau','src/server/npc/NpcMotionIntent.luau'):
                text=read(file).replace('generation += 1','generation = generation + 1')
                target=Path(tmp)/Path(file).with_suffix('.lua').name
                target.write_text(text,encoding='utf-8');files.append(str(target))
            subprocess.run([lua,str(ROOT/'system/verify/mnpc_pose_binding_m629.lua'),*files],check=True,timeout=15)

    def test_both_agents_register_independent_of_pose(self):
        m=read('src/server/monster/MonsterAgentLifecycle.luau')
        n=read('src/server/npc/NpcCombatAIService.luau')
        for source in (m,n):
            self.assertIn('WaitForChild("MnpcPoseBinding")',source)
            self.assertIn('PoseBinding.new()',source)
            self.assertIn('agent.poseBinding:Commit(ticket,',source)
            self.assertIn('agent.poseBinding:Close()',source)
        before=m.split('local function registerModel',1)[1].split('local function ready()',1)[0]
        self.assertNotIn('AnimatorOf(',before)
        self.assertNotIn('Game1MnpcRigReady',before)
        self.assertIn('Navigation.Initialize(agent)',before)
        self.assertLess(m.index('Scheduler.Register(agent'),m.index('            ready()'))
        self.assertIn('Presentation.DestroyBinding(tracks)',m)
        bind=n.split('function NpcCombatAIService.Bind(',1)[1].split('function NpcCombatAIService.AttachPresentation',1)[0]
        self.assertNotIn('presentation:',bind)
        self.assertIn('Navigator.new(root, humanoid)',bind)
        self.assertIn('motion = MotionIntent.new(poseBinding)',bind)
        self.assertIn('Scheduler.Register(agent',bind)
        spawn=read('src/server/npc/NpcSpawnerService.luau')
        self.assertLess(spawn.index('NpcCombatAIService.Bind(entity'),spawn.index('pcall(NpcAnimationService.Create'))
        self.assertLess(spawn.index('entity.Destroying:Connect'),spawn.index('pcall(NpcAnimationService.Create'))
        self.assertLess(spawn.index('NpcCombatAIService.AttachPresentation(entity'),spawn.index('MnpcLifecycle.MarkRigReady(entity)'))
        self.assertIn('presentation.Destroy()\n        release(state, entity, false)',spawn)

    def test_combat_actions_require_real_binding_and_old_monster_attack_bodies_preserved(self):
        hashes=json.loads(read('system/verify/ai_protected_m617.json'))
        for file, signature, result in (
            ('src/server/monster/MonsterAttackExecutor.luau','function MonsterAttackExecutor.Begin(agent: any, target: Model, movement: any, random: Random)','return end'),
            ('src/server/monster/MonsterSkillCast.luau','function Cast.TryBegin(agent: any,target: Model): boolean','return false end'),
        ):
            source=read(file)
            gate='    if not agent.poseBinding:IsReady() then '+result+'\n'
            self.assertIn(signature+'\n'+gate,source)
            self.assertEqual(hashlib.sha256(source.replace(gate,'',1).encode()).hexdigest(),hashes[file])
        presentation=read('src/server/monster/MonsterCombatPresentation.luau')
        start=presentation.index('-- Combat AI tracks are distinct')
        end=presentation.index('function MonsterCombatPresentation.PlayCombatIdle',start)
        self.assertEqual(hashlib.sha256((presentation[:start]+presentation[end:]).encode()).hexdigest(),hashes['src/server/monster/MonsterCombatPresentation.luau'])
        npc=read('src/server/npc/NpcCombatAIService.luau')
        attack=npc.split('local function beginAttack(',1)[1].split('local function tickAgent(',1)[0]
        self.assertLess(attack.index('agent.poseBinding:IsReady()'),attack.index('agent.attacking = true'))
        self.assertIn('agent.presentation.StartAttack(row, percent)',attack)
        self.assertIn('agent.presentation.ContinueAttack(percent)',attack)
        self.assertIn('attackTiming(agent, row, percent, track)',attack)
        self.assertIn('task.delay(math.max(0, hitAt - elapsed)',attack)

    def test_no_new_runtime_dormancy_or_polling(self):
        for file in ('src/server/actor/MnpcPoseBinding.luau','src/server/npc/NpcMotionIntent.luau'):
            source=read(file)
            for forbidden in ('Instance.new','Heartbeat','task.wait','RemoteEvent','LoadAnimation','DamageService','EntityHitboxService'):
                self.assertNotIn(forbidden,source)
        source=read('src/server/monster/MonsterSpawnerService.luau')
        self.assertLess(source.index('model:SetAttribute("MonsterSpawning", true)'),source.index('MnpcLifecycle.Publish(model'))
        self.assertLess(source.index('model:SetAttribute("MonsterHomePosition", navigationRoot.Position)'),source.index('MnpcLifecycle.Publish(model'))
        self.assertIn('EntityHitboxService.Attach(model, visual)',source)
        self.assertIn('EntityHitboxService.Attach(entity, visual)',read('src/server/npc/NpcSpawnerService.luau'))

if __name__=='__main__': unittest.main()
