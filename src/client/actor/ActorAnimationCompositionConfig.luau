-- Roblox Studio: StarterPlayer.StarterPlayerScripts.game1Client.MonsterAnimation.ActorAnimationCompositionConfig (ModuleScript)
-- Client-only limits for monster upper-body-over-locomotion composition.
local Config = {
	MaxComposedActors = 32, -- shared resident limit, including idle and pending samplers
	MaxDistance = 140,
	EntryBlendSeconds = 0.10,
	ExitBlendSeconds = 0.08,
	SamplerIdleTtlSeconds = 8,
	SamplerAnchorInterval = 0.50,
	BottomLeafBandFraction = 0.28,
	MaxLowerBodyFraction = 0.62,
	MovementDirectionMinSpeed = 0.35,
}

return table.freeze(Config)
