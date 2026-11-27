-- Execute the actual pure shared phase module with standard Lua.
math.clamp = math.clamp or function(v, a, b) return math.max(a, math.min(b, v)) end
table.freeze = table.freeze or function(t) return t end
local Phase = dofile('src/shared/combat/AttackPresentationPhase.luau')
local state = {startAt=100, duration=2, endAt=102}
local function near(a,b) assert(math.abs(a-b)<1e-8, tostring(a)..' != '..tostring(b)) end
local phase, rate, ends = Phase.Resolve(state, 100.5)
near(phase, .25); near(rate, 1); near(ends,102)
near(Phase.Resolve(state, 99),0); near(Phase.Resolve(state, 103),1)
state.bounceAt=101; state.bouncePhase=.5; state.reverseSpeed=2; state.endAt=101.62
phase, rate, ends = Phase.Resolve(state,101.2)
near(phase,.3); near(rate,-2); near(ends,101.62)
phase, rate = Phase.Resolve(state,101.6)
near(phase,0); near(rate,0)
print('M612 phase OK')
