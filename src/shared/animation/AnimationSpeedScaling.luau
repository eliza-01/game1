local Registry = require(script.Parent:WaitForChild("AnimationSpeedScalingRegistry"))

local AnimationSpeedScaling = {}

AnimationSpeedScaling.MinPercent = 1
AnimationSpeedScaling.MaxPercent = 400
AnimationSpeedScaling.DebugOverrideAttribute = "MovementDebugAnimationSpeedPercentOverride"

local function finite(value: any, fallback: number): number
    local numeric = tonumber(value)
    if numeric == nil or numeric ~= numeric or numeric == math.huge or numeric == -math.huge then
        return fallback
    end
    return numeric
end

local function targetForModel(model: Model): (string, string)
    if model:GetAttribute("Game1MonsterRuntime") == true or model:GetAttribute("MonsterSlug") ~= nil then
        return "monster", string.lower(tostring(model:GetAttribute("MonsterSlug") or ""))
    end
    return "character", string.lower(tostring(
        model:GetAttribute("AnimationProfileId")
            or model:GetAttribute("CharacterArchetype")
            or model:GetAttribute("NPCSlug")
            or ""
    ))
end

function AnimationSpeedScaling.Rule(targetType: any, targetId: any, channel: any): any?
    local byType = Registry.profiles[string.lower(tostring(targetType or ""))]
    local profile = byType and byType[string.lower(tostring(targetId or ""))]
    return profile and profile[string.lower(tostring(channel or ""))] or nil
end

function AnimationSpeedScaling.ResolvePercent(targetType: any, targetId: any, channel: any, statValue: any): number
    local rule = AnimationSpeedScaling.Rule(targetType, targetId, channel)
    if not rule then
        return 100
    end
    local unitsPerPercent = math.max(0.001, finite(rule.unitsPerPercent, 1))
    local value = math.max(0, finite(statValue, 0))
    return math.clamp(value / unitsPerPercent, AnimationSpeedScaling.MinPercent, AnimationSpeedScaling.MaxPercent)
end

function AnimationSpeedScaling.ResolveForModel(model: Model, channel: any): number
    local override = tonumber(model:GetAttribute(AnimationSpeedScaling.DebugOverrideAttribute))
    if override ~= nil then
        return math.clamp(override, AnimationSpeedScaling.MinPercent, AnimationSpeedScaling.MaxPercent)
    end

    local targetType, targetId = targetForModel(model)
    local rule = AnimationSpeedScaling.Rule(targetType, targetId, channel)
    if not rule then
        return 100
    end
    return AnimationSpeedScaling.ResolvePercent(targetType, targetId, channel, model:GetAttribute(tostring(rule.stat or "")))
end

function AnimationSpeedScaling.ResolveScaleForModel(model: Model, channel: any): number
    return AnimationSpeedScaling.ResolveForModel(model, channel) / 100
end

return table.freeze(AnimationSpeedScaling)
