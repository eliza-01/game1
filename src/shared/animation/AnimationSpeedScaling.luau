local Registry = require(script.Parent:WaitForChild("AnimationSpeedScalingRegistry"))

local AnimationSpeedScaling = {}

AnimationSpeedScaling.MinPercent = 1
AnimationSpeedScaling.MaxPercent = 400
AnimationSpeedScaling.MinUnitsPerPercent = 0.001
AnimationSpeedScaling.MaxUnitsPerPercent = 1000
AnimationSpeedScaling.DebugUnitsPerPercentPrefix = "MovementDebugAnimationUnitsPerPercent_"
local function finite(value: any, fallback: number): number
    local numeric = tonumber(value)
    if numeric == nil or numeric ~= numeric or numeric == math.huge or numeric == -math.huge then
        return fallback
    end
    return numeric
end


function AnimationSpeedScaling.DebugUnitsPerPercentAttribute(channel: any): string
    local normalized = string.lower(tostring(channel or ""))
    return AnimationSpeedScaling.DebugUnitsPerPercentPrefix .. normalized
end

function AnimationSpeedScaling.TargetForModel(model: Model): (string, string)
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


function AnimationSpeedScaling.ResolveDetailsForModel(model: Model, channel: any): any
    local normalizedChannel = string.lower(tostring(channel or ""))
    local targetType, targetId = AnimationSpeedScaling.TargetForModel(model)
    local rule = AnimationSpeedScaling.Rule(targetType, targetId, normalizedChannel)
    if not rule then
        return {
            targetType = targetType,
            targetId = targetId,
            channel = normalizedChannel,
            stat = "",
            statValue = nil,
            unitsPerPercent = nil,
            percent = 100,
            hasRule = false,
        }
    end

    local stat = tostring(rule.stat or "")
    local statValue = math.max(0, finite(model:GetAttribute(stat), 0))
    local authoredUnitsPerPercent = math.clamp(
        finite(rule.unitsPerPercent, 1),
        AnimationSpeedScaling.MinUnitsPerPercent,
        AnimationSpeedScaling.MaxUnitsPerPercent
    )
    local overrideAttribute = AnimationSpeedScaling.DebugUnitsPerPercentAttribute(normalizedChannel)
    local debugUnitsPerPercent = tonumber(model:GetAttribute(overrideAttribute))
    local unitsPerPercent = authoredUnitsPerPercent
    if debugUnitsPerPercent ~= nil then
        unitsPerPercent = math.clamp(
            finite(debugUnitsPerPercent, authoredUnitsPerPercent),
            AnimationSpeedScaling.MinUnitsPerPercent,
            AnimationSpeedScaling.MaxUnitsPerPercent
        )
    end
    local percent = math.clamp(
        statValue / unitsPerPercent,
        AnimationSpeedScaling.MinPercent,
        AnimationSpeedScaling.MaxPercent
    )
    return {
        targetType = targetType,
        targetId = targetId,
        channel = normalizedChannel,
        stat = stat,
        statValue = statValue,
        authoredUnitsPerPercent = authoredUnitsPerPercent,
        debugUnitsPerPercent = debugUnitsPerPercent,
        unitsPerPercent = unitsPerPercent,
        percent = percent,
        hasRule = true,
    }
end

function AnimationSpeedScaling.ResolveForModel(model: Model, channel: any): number
    return AnimationSpeedScaling.ResolveDetailsForModel(model, channel).percent
end

function AnimationSpeedScaling.ResolveScaleForModel(model: Model, channel: any): number
    return AnimationSpeedScaling.ResolveForModel(model, channel) / 100
end

return table.freeze(AnimationSpeedScaling)
