--!strict
local Policy = {}
function Policy.Allows(attacker: Model?, target: Model): boolean
    local source = if attacker then attacker:GetAttribute("Game1GameplayTestOwner") else nil
    local destination = target:GetAttribute("Game1GameplayTestOwner")
    if source == nil and destination == nil then return true end
    if source == nil or source ~= destination or not attacker then return false end
    local sourceKind = attacker:GetAttribute("GameplayTestKind")
    local targetKind = target:GetAttribute("GameplayTestKind")
    if sourceKind == "group" and attacker:GetAttribute("GameplayTestArmed") ~= true then return false end
    if targetKind == "group" and target:GetAttribute("GameplayTestArmed") ~= true then return false end
    return (sourceKind == "player" and (targetKind == "line" or targetKind == "group"))
        or ((sourceKind == "line" or sourceKind == "group") and targetKind == "player")
end
return table.freeze(Policy)
