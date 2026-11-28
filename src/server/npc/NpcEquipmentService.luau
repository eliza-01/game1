-- NPC equipment lifecycle. Registered templates are read-only; loadouts persist
-- independently. The client attachment controller owns animated bone following.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Loadouts = require(Shared:WaitForChild("npc"):WaitForChild("NpcEquipmentRegistry"))
local WeaponAttackMovement = require(Shared:WaitForChild("weapon"):WaitForChild("WeaponAttackMovement"))
local WeaponEquipService = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponEquipService"))
local NpcEquipmentService = {}
-- Authored context is available before a visual or bone socket exists.
-- Effective mounted context is still validated by Equip (same fallback as M630).
function NpcEquipmentService.Resolve(npcSlug: string): any
    local loadout = (Loadouts.loadouts or {})[npcSlug] or {}
    local items = {}
    local primaryType = "hands"
    local found = false
    for _, hand in ipairs({"right", "left"}) do
        local slug = tostring(loadout[hand] or "")
        if slug ~= "" then
            local row, template = WeaponEquipService.ResolveVisual(slug)
            table.insert(items, table.freeze({hand = hand, slug = slug}))
            if template and not found then
                found = true
                primaryType = string.lower(tostring(row.weaponType or "hands"))
            end
        end
    end
    return table.freeze({items = table.freeze(items), weaponType = primaryType,
        weaponSet = WeaponAttackMovement.AnimationSetForType(primaryType)})
end

function NpcEquipmentService.Equip(entity: Model, npcSlug: string, context: any, rigLease: any): string
    -- Unarmed is an equipment context with its own idle, combat and attack clips.
    -- Combat damage is still the normal server-authoritative NPC damage path.
    local set = WeaponAttackMovement.AnimationSetForType("hands")
    local hasWeapon = false
    local primaryType = "hands"
    for _, item in ipairs(context.items) do
        local hand = item.hand
        local model, definition, err = WeaponEquipService.EquipVisual(entity, item.slug, hand,
            if hand == "right" then "EquippedWeaponRight" else "EquippedWeaponLeft")
        if not model then
            warn("[game1][npc] cannot equip " .. npcSlug .. " " .. hand .. ": " .. tostring(err))
        else
            rigLease:OwnEquipment(model)
            if not hasWeapon then
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
