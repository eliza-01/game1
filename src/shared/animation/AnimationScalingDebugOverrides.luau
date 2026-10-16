-- Roblox runtime/Studio authoring override access, kept out of policy and math.
local Workspace = game:GetService("Workspace")
local Overrides = {}

function Overrides.ClipRule(assetId: string, prefix: string): any?
    local debugUnits = Workspace:GetAttribute(prefix .. assetId)
    if not (typeof(debugUnits) == "number" and debugUnits > 0) then
        return nil
    end
    local stat = Workspace:GetAttribute(prefix .. assetId .. "_Stat")
    return {
        stat = if stat == "RunSpeed" then stat else "AttackSpeed",
        unitsPerPercent = debugUnits,
    }
end

function Overrides.ModelUnits(model: Model, attributeName: string): number?
    return tonumber(model:GetAttribute(attributeName))
end

return table.freeze(Overrides)
