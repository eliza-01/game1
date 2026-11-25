-- Studio Command Bar (server, Play): pure retreat geometry/cadence smoke checks.
local Retreat = require(game:GetService("ServerScriptService").Game1Server.monster.MonsterRangedRetreat)
local points = Retreat.Candidates(Vector3.new(0,5,0), Vector3.new(0,9,10), 40, 10)
assert(#points > 0 and points[1] == Vector3.new(0,5,-4))
assert(#Retreat.Candidates(Vector3.zero, Vector3.new(0,0,40), 40, 10) == 0)
assert(#Retreat.Candidates(Vector3.zero, Vector3.zero, 40, 10) == 0)
local diagonal = Retreat.Candidates(Vector3.zero, Vector3.new(3,0,4), 40, 2)[1]
assert((diagonal - Vector3.new(-1.2,0,-1.6)).Magnitude < 0.001)
local p = Retreat.FitPercent({playbackDuration=2}, 100)
assert(math.abs(p - 125) < 0.001 and math.abs(2 - 2*100/p - .4) < 0.001)
assert(Retreat.FitPercent({playbackDuration=1}, 400) == 400)
print("[M527] retreat direction, range, budget, and cadence cap OK")
