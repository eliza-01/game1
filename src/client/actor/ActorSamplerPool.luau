-- Exactly one pool per client for NPC and monster locomotion composition.
local Config = require(script.Parent:WaitForChild("ActorAnimationCompositionConfig"))
local Pool = require(script.Parent:WaitForChild("SamplerPool"))
return Pool.new(Config.MaxComposedActors, Config.SamplerIdleTtlSeconds, os.clock)
