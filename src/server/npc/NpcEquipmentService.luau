-- NPC equipment lifecycle. Registered templates are read-only; loadouts persist
-- independently. The client attachment controller owns animated bone following.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local WeaponRegistry = require(Shared:WaitForChild("weapon"):WaitForChild("WeaponRegistry"))
local Loadouts = require(Shared:WaitForChild("npc"):WaitForChild("NpcEquipmentRegistry"))
local WeaponAttackMovement = require(Shared:WaitForChild("weapon"):WaitForChild("WeaponAttackMovement"))
local WeaponEquipService = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponEquipService"))
local NpcEquipmentService = {}
function NpcEquipmentService.Equip(entity: Model, npcSlug: string): string
    local loadout = (Loadouts.loadouts or {})[npcSlug] or {}
    -- Unarmed is an equipment context with its own idle, combat and attack clips.
    -- Combat damage is still the normal server-authoritative NPC damage path.
    local set = WeaponAttackMovement.AnimationSetForType("hands")
    local preferredHand = { "right", "left" }
    local hasWeapon = false
    local primaryType = "hands"
    for _, hand in ipairs(preferredHand) do
        local slug = tostring(loadout[hand] or "")
        if slug ~= "" then
            local model, definition, err = WeaponEquipService.EquipVisual(entity, slug, hand,
                if hand == "right" then "EquippedWeaponRight" else "EquippedWeaponLeft")
            if not model then
                warn("[game1][npc] cannot equip " .. npcSlug .. " " .. hand .. ": " .. tostring(err))
            elseif not hasWeapon then
                hasWeapon = true
                primaryType = string.lower(tostring(definition.weaponType or "hands"))
                set = WeaponAttackMovement.AnimationSetForType(primaryType)
            end
        end
    end
    entity:SetAttribute("NpcWeaponType", primaryType)
    entity:SetAttribute("NpcWeaponSet", set)
    return set
end
return table.freeze(NpcEquipmentService)
