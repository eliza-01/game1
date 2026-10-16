-- Published profile and clip-rule selection only. No Workspace/debug dependencies.
local Registry = require(script.Parent:WaitForChild("AnimationSpeedScalingRegistry"))
local Policy = {}

function Policy.TargetForModel(model: Model): (string, string)
    if model:GetAttribute("Game1MonsterRuntime") == true or model:GetAttribute("MonsterSlug") ~= nil then
        return "monster", string.lower(tostring(model:GetAttribute("MonsterSlug") or ""))
    end
    return "humanoid", "all"
end

function Policy.Rule(targetType: any, targetId: any, channel: any): any?
    local kind = string.lower(tostring(targetType or ""))
    local id = string.lower(tostring(targetId or ""))
    if kind == "character" or kind == "npc" or kind == "humanoid" then
        kind, id = "humanoid", "all"
    end
    local byType = Registry.profiles[kind]
    local profile = byType and byType[id]
    return profile and profile[string.lower(tostring(channel or ""))] or nil
end

function Policy.CustomRule(assetId: string): any?
    return Registry.custom and Registry.custom[assetId] or nil
end

function Policy.Catalog(): any
    return Registry.catalog or {}
end

return table.freeze(Policy)
