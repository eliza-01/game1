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

-- Saved camera defaults are authoritative; Studio debug uses an ephemeral copy.
function GameOptions.CameraSettings(): {[string]: number}
    local source = Registry.camera or {}
    return {
        targetHeight = math.clamp(finite(source.targetHeight, 5.5), 0, 12),
        distance = math.clamp(finite(source.distance, 10), 4, 18),
        pitchDegrees = math.clamp(finite(source.pitchDegrees, -12), -65, 60),
        characterX = math.clamp(finite(source.characterX, 0.5), 0.2, 0.8),
        characterY = math.clamp(finite(source.characterY, 0.5), 0.2, 0.8),
        cursorX = math.clamp(finite(source.cursorX, 0.5), 0.1, 0.9),
        cursorY = math.clamp(finite(source.cursorY, 0.5), 0.1, 0.9),
    }
end

-- Configured visual profiles are generated from Asset Manager Options.
function GameOptions.HealthUiSettings(device: string): {[string]: any}
    local profiles = Registry.healthUi or {}
    return profiles[device] or profiles.desktop or {}
end

function GameOptions.ShowPublishedDebugControls(device: string): boolean
    local settings = (Registry.debugUi or {})[device] or {}
    return settings.showPublishedControls == true
end

return table.freeze(GameOptions)
