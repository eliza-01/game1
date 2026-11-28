-- Execute the actual common binding and NPC intent modules (Lua adapter only).
table.freeze = table.freeze or function(t) return t end
local Binding = dofile(arg[1])
local Intent = dofile(arg[2])
local monster, npc = Binding.new(), Binding.new()
assert(not monster:IsReady() and not npc:IsReady())
local mt, nt = monster:Begin(), npc:Begin()
assert(mt ~= nt and not monster:Commit(nt, {}))
assert(monster:Begin() == nil and not monster:IsReady())
local motion = Intent.new(npc)
-- AI can change motion/return intent before any Animator/presentation exists.
motion.SetCombatActive(true)
motion.SetCombatMoving(true)
motion.SetReturnActive(true)
motion.SetReturnMoving(true)
local states, calls = {}, 0
local real = {}
for _, name in ipairs({'SetCombatActive','SetCombatMoving','SetReturnActive','SetReturnMoving'}) do
    real[name] = function(v) states[name]=v; calls=calls+1 end
end
assert(npc:Commit(nt, real))
motion.Replay()
assert(calls == 4 and states.SetCombatActive and states.SetCombatMoving and states.SetReturnActive and states.SetReturnMoving)
motion.SetReturnMoving(false)
motion.SetReturnActive(false)
assert(calls == 6 and not states.SetReturnMoving and not states.SetReturnActive)
assert(npc:Release() == real and not npc:IsReady())
motion.SetCombatMoving(false)
assert(calls == 6)
local new = npc:Begin()
assert(new ~= nt and not npc:Commit(nt, real))
assert(npc:Commit(new, real))
motion.Replay()
assert(not states.SetCombatMoving and not states.SetReturnMoving)
assert(npc:Close() == real and npc:Close() == nil and npc:Begin() == nil and not npc:Commit(new,real))
-- Cancellation while native track loading is still in flight.
assert(monster:Abort(mt))
local fresh = monster:Begin()
assert(fresh ~= mt and not monster:Commit(mt, {}))
assert(monster:Close() == nil and not monster:Commit(fresh, {}))
local reincarnated = Binding.new()
local nextTicket = reincarnated:Begin()
assert(nextTicket ~= mt and not reincarnated:Commit(mt, {}))
assert(not reincarnated:Commit(nextTicket,nil))
local pose = {animator = true}
assert(reincarnated:Commit(nextTicket,pose) and reincarnated:IsReady() and reincarnated:Get() == pose)
assert(not reincarnated:Commit(nextTicket, {}))
assert(reincarnated:Close() == pose)
print('MNPC binding + NPC motion intent oracle passed')
