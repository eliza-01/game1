-- Public compatibility facade for character, NPC and monster animation controllers.
-- Profile selection, math and Workspace debug access live in owned components.
local Formula = require(script.Parent:WaitForChild("AnimationScalingFormula"))
local Policy = require(script.Parent:WaitForChild("AnimationScalingPolicy"))
local DebugOverrides = require(script.Parent:WaitForChild("AnimationScalingDebugOverrides"))

local AnimationSpeedScaling = {}

AnimationSpeedScaling.MinPercent = Formula.MinPercent
AnimationSpeedScaling.MaxPercent = Formula.MaxPercent
AnimationSpeedScaling.MinUnitsPerPercent = Formula.MinUnitsPerPercent
AnimationSpeedScaling.MaxUnitsPerPercent = Formula.MaxUnitsPerPercent
AnimationSpeedScaling.CustomDebugPrefix = "Game1CustomScaling_"
AnimationSpeedScaling.DebugUnitsPerPercentPrefix = "MovementDebugAnimationUnitsPerPercent_"

function AnimationSpeedScaling.DebugUnitsPerPercentAttribute(channel: any): string
    local normalized = string.lower(tostring(channel or ""))
    return AnimationSpeedScaling.DebugUnitsPerPercentPrefix .. normalized
end

-- All Characters and NPCs share "humanoid/all"; monsters retain their own profile.
function AnimationSpeedScaling.TargetForModel(model: Model): (string, string)
    return Policy.TargetForModel(model)
end

function AnimationSpeedScaling.Rule(targetType: any, targetId: any, channel: any): any?
    return Policy.Rule(targetType, targetId, channel)
end

function AnimationSpeedScaling.ResolvePercent(targetType: any, targetId: any, channel: any, statValue: any): number
    local rule = AnimationSpeedScaling.Rule(targetType, targetId, channel)
    if not rule then
        return 100
    end
    return Formula.RulePercent(statValue, rule.unitsPerPercent)
end

-- Numeric suffix IDs remain stable across asset rename / local file migrations.
function AnimationSpeedScaling.AssetId(value: any): string
    local id = tostring(value or ""):match("(%d+)$")
    return id or ""
end

function AnimationSpeedScaling.Catalog(): any
    return Policy.Catalog()
end

function AnimationSpeedScaling.RuleForAnimation(model: Model, channel: any, animationId: any): (any?, boolean)
    local id = AnimationSpeedScaling.AssetId(animationId)
    if id ~= "" then
        local authored = Policy.CustomRule(id)
        local debugRule = DebugOverrides.ClipRule(id, AnimationSpeedScaling.CustomDebugPrefix)
        if debugRule then
            return debugRule, true
        end
        if authored then
            return authored, true
        end
    end
    local targetType, targetId = AnimationSpeedScaling.TargetForModel(model)
    return AnimationSpeedScaling.Rule(targetType, targetId, channel), false
end

function AnimationSpeedScaling.ResolveDetailsForModel(model: Model, channel: any, statValueOverride: any?, animationId: any?): any
    local normalizedChannel = string.lower(tostring(channel or ""))
    local targetType, targetId = AnimationSpeedScaling.TargetForModel(model)
    local rule, isCustom = AnimationSpeedScaling.RuleForAnimation(model, normalizedChannel, animationId)
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
    local rawStatValue = if statValueOverride ~= nil and not isCustom then statValueOverride else model:GetAttribute(stat)
    local statValue = Formula.StatValue(rawStatValue)
    local authoredUnitsPerPercent = Formula.AuthoredUnits(rule.unitsPerPercent)
    local overrideAttribute = AnimationSpeedScaling.DebugUnitsPerPercentAttribute(normalizedChannel)
    local debugUnitsPerPercent = DebugOverrides.ModelUnits(model, overrideAttribute)
    local unitsPerPercent = authoredUnitsPerPercent
    if debugUnitsPerPercent ~= nil and not isCustom then
        unitsPerPercent = Formula.DebugUnits(debugUnitsPerPercent, authoredUnitsPerPercent)
    end
    local percent = Formula.DetailsPercent(statValue, unitsPerPercent)
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
        custom = isCustom,
    }
end

function AnimationSpeedScaling.ResolveForModel(model: Model, channel: any): number
    return AnimationSpeedScaling.ResolveDetailsForModel(model, channel).percent
end

function AnimationSpeedScaling.ResolveForModelWithStatValue(model: Model, channel: any, statValue: any): number
    return AnimationSpeedScaling.ResolveDetailsForModel(model, channel, statValue).percent
end

function AnimationSpeedScaling.ResolveScaleForModel(model: Model, channel: any): number
    return AnimationSpeedScaling.ResolveForModel(model, channel) / 100
end

function AnimationSpeedScaling.ResolveForAnimation(model: Model, channel: any, animationId: any, statValueOverride: any?): number
    return AnimationSpeedScaling.ResolveDetailsForModel(model, channel, statValueOverride, animationId).percent
end

function AnimationSpeedScaling.ResolveScaleForAnimation(model: Model, channel: any, animationId: any, statValueOverride: any?): number
    return AnimationSpeedScaling.ResolveForAnimation(model, channel, animationId, statValueOverride) / 100
end

-- Existing tracks update only when explicitly requested by the Studio debug UI.
-- Controllers retain ownership of subsequent Play/AdjustSpeed calls.
function AnimationSpeedScaling.RefreshPlaying(model: Model, animationId: any)
    local desiredId = AnimationSpeedScaling.AssetId(animationId)
    if desiredId == "" then return end
    local metadata = AnimationSpeedScaling.Catalog()[desiredId]
    local channel = metadata and metadata.channel or "idle"
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("Animator") then
            for _, track in ipairs(descendant:GetPlayingAnimationTracks()) do
                local trackId = AnimationSpeedScaling.AssetId(track.Animation and track.Animation.AnimationId)
                if trackId == desiredId and track.Speed > 0 then
                    track:AdjustSpeed(AnimationSpeedScaling.ResolveScaleForAnimation(model, channel, desiredId))
                end
            end
        end
    end
end

return table.freeze(AnimationSpeedScaling)
