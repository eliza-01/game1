local Registry = require(script.Parent:WaitForChild("GameOptionsRegistry"))

local GameOptions = {}

local function finite(value: any, fallback: number): number
	local number = tonumber(value)
	if number == nil or number ~= number or number == math.huge or number == -math.huge then
		return fallback
	end
	return number
end

function GameOptions.CombatStateDurationSeconds(): number
	local combat = Registry.combat or {}
	return math.clamp(finite(combat.stateDurationSeconds, 6), 0, 3600)
end

function GameOptions.CharacterLifePlaybackPercent(slot: any): number
	local life = Registry.characterAnimations or {}
	local normalized = string.lower(tostring(slot or ""))
	if normalized == "death" then
		return math.clamp(finite(life.deathPlaybackPercent, 100), 1, 400)
	elseif normalized == "revive" then
		return math.clamp(finite(life.revivePlaybackPercent, 100), 1, 400)
	end
	return 100
end

return table.freeze(GameOptions)
