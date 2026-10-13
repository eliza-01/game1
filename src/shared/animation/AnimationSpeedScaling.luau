local Registry = require(script.Parent:WaitForChild("AnimationSpeedScalingRegistry"))
local Workspace = game:GetService("Workspace")

local AnimationSpeedScaling = {}

AnimationSpeedScaling.MinPercent = 1
AnimationSpeedScaling.MaxPercent = 400
AnimationSpeedScaling.MinUnitsPerPercent = 0.001
AnimationSpeedScaling.MaxUnitsPerPercent = 1000
AnimationSpeedScaling.CustomDebugPrefix = "Game1CustomScaling_"
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

-- All playable Characters and NPCs use the same four animation-speed rules.
-- Monster tuning remains an independent profile.
function AnimationSpeedScaling.TargetForModel(model: Model): (string, string)
    if model:GetAttribute("Game1MonsterRuntime") == true or model:GetAttribute("MonsterSlug") ~= nil then
        return "monster", string.lower(tostring(model:GetAttribute("MonsterSlug") or ""))
    end
    return "humanoid", "all"
end

function AnimationSpeedScaling.Rule(targetType: any, targetId: any, channel: any): any?
    local kind = string.lower(tostring(targetType or ""))
    local id = string.lower(tostring(targetId or ""))
    if kind == "character" or kind == "npc" or kind == "humanoid" then
        kind, id = "humanoid", "all"
    end
    local byType = Registry.profiles[kind]
    local profile = byType and byType[id]
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


-- Clip-level policy has priority over the state-level rule. Roblox asset IDs
-- are stable through display-name and local filename migrations.
function AnimationSpeedScaling.AssetId(value: any): string
    local id = tostring(value or ""):match("(%d+)$")
    return id or ""
end

function AnimationSpeedScaling.Catalog(): any
    return Registry.catalog or {}
end

function AnimationSpeedScaling.RuleForAnimation(model: Model, channel: any, animationId: any): (any?, boolean)
    local id = AnimationSpeedScaling.AssetId(animationId)
    if id ~= "" then
        local override = Registry.custom and Registry.custom[id]
        local debugUnits = Workspace:GetAttribute(AnimationSpeedScaling.CustomDebugPrefix .. id)
        if typeof(debugUnits) == "number" and debugUnits > 0 then
            local stat = Workspace:GetAttribute(AnimationSpeedScaling.CustomDebugPrefix .. id .. "_Stat")
            return {stat = if stat == "RunSpeed" then stat else "AttackSpeed", unitsPerPercent = debugUnits}, true
        end
        if override then
            return override, true
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
    local statValue = math.max(0, finite(rawStatValue, 0))
    local authoredUnitsPerPercent = math.clamp(
        finite(rule.unitsPerPercent, 1),
        AnimationSpeedScaling.MinUnitsPerPercent,
        AnimationSpeedScaling.MaxUnitsPerPercent
    )
    local overrideAttribute = AnimationSpeedScaling.DebugUnitsPerPercentAttribute(normalizedChannel)
    local debugUnitsPerPercent = tonumber(model:GetAttribute(overrideAttribute))
    local unitsPerPercent = authoredUnitsPerPercent
    if debugUnitsPerPercent ~= nil and not isCustom then
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

-- Studio debug changes affect already playing tracks without respawning actors.
-- Animation state controllers remain authoritative for later Play/AdjustSpeed calls.
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
