local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local WeaponShared = Shared:WaitForChild("weapon")
local WeaponRegistry = require(WeaponShared:WaitForChild("WeaponRegistry"))
local CharacterStatsService = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterStatsService"))

local WeaponEquipService = {}
local EQUIPPED_NAME = "EquippedWeapon"

local RIGHT_SOCKET_NAMES = { "Weapon_R_Bone", "weapon_r", "Weapon_R", "WeaponR" }
local LEFT_SOCKET_NAMES = { "Weapon_L_Bone", "weapon_l", "Weapon_L", "WeaponL" }

local function findByStudioPath(studioPath: string): Instance?
    if string.sub(studioPath, 1, 14) ~= "ServerStorage." then
        return nil
    end
    local node: Instance = ServerStorage
    for segment in string.gmatch(string.sub(studioPath, 15), "[^%.]+") do
        local child = node:FindFirstChild(segment)
        if not child then
            return nil
        end
        node = child
    end
    return node
end

local function findCharacterBone(character: Model, names: { string }): Bone?
    local visual = character:FindFirstChild("Visual")
    if not visual then
        return nil
    end
    for _, name in ipairs(names) do
        local found = visual:FindFirstChild(name, true)
        if found and found:IsA("Bone") then
            return found
        end
    end
    return nil
end

local function socketNames(weaponType: string): { string }
    return if string.lower(weaponType) == "bow" then LEFT_SOCKET_NAMES else RIGHT_SOCKET_NAMES
end

local function prepareWeapon(model: Model)
    for _, descendant in model:GetDescendants() do
        if descendant:IsA("Humanoid") or descendant:IsA("AnimationController") then
            descendant:Destroy()
        elseif descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
            descendant.Massless = true
        end
    end
end

local function clearWeapon(character: Model)
    local old = character:FindFirstChild(EQUIPPED_NAME)
    if old then
        old:Destroy()
    end
end

function WeaponEquipService.Unequip(character: Model)
    clearWeapon(character)
    character:SetAttribute("EquippedWeaponSlug", "")
    character:SetAttribute("EquippedWeaponType", "")
    character:SetAttribute("EquippedWeaponRarity", "")
    character:SetAttribute("AnimationWeaponSet", "hands")
    CharacterStatsService.ApplyModifiers(character, {})
end

function WeaponEquipService.Equip(character: Model, slugValue: any): (boolean, string?)
    local slug = string.lower(tostring(slugValue or ""))
    local row = WeaponRegistry.weapons and WeaponRegistry.weapons[slug]
    if not row then
        WeaponEquipService.Unequip(character)
        return false, "weapon is not registered: " .. slug
    end

    local template = findByStudioPath(tostring(row.serverStoragePath or ""))
    if not template or not template:IsA("Model") then
        WeaponEquipService.Unequip(character)
        return false, "weapon template is not synced into ServerStorage: " .. slug
    end

    local targetBone = findCharacterBone(character, socketNames(tostring(row.weaponType or "")))
    if not targetBone then
        WeaponEquipService.Unequip(character)
        return false, "character has no compatible weapon socket bone"
    end

    clearWeapon(character)
    local weapon = template:Clone()
    weapon.Name = EQUIPPED_NAME
    prepareWeapon(weapon)
    weapon:SetAttribute("Game1WeaponAttachment", true)
    weapon:SetAttribute("WeaponTargetBoneName", targetBone.Name)
    weapon:SetAttribute("WeaponSlug", slug)
    weapon:SetAttribute("WeaponType", tostring(row.weaponType or ""))
    weapon:SetAttribute("WeaponRarity", tostring(row.rarity or ""))
    weapon:SetAttribute("WeaponAttachmentMode", "pivot")
    weapon:PivotTo(targetBone.WorldCFrame)
    weapon.Parent = character

    character:SetAttribute("EquippedWeaponSlug", slug)
    character:SetAttribute("EquippedWeaponType", tostring(row.weaponType or ""))
    character:SetAttribute("EquippedWeaponRarity", tostring(row.rarity or ""))
    character:SetAttribute("AnimationWeaponSet", tostring(row.weaponType or "hands"))
    CharacterStatsService.ApplyModifiers(character, row.statModifiers or {})
    return true, nil
end

function WeaponEquipService.GetAvailable(slugValue: any): any?
    local slug = string.lower(tostring(slugValue or ""))
    if slug == "" then
        return nil
    end
    return WeaponRegistry.weapons and WeaponRegistry.weapons[slug] or nil
end

function WeaponEquipService.ListAvailable(): { any }
    local rows = {}
    for slug, row in pairs(WeaponRegistry.weapons or {}) do
        if tonumber(row.modelAssetId) then
            table.insert(rows, {
                slug = tostring(slug),
                nameEn = tostring(row.nameEn or slug),
                nameRu = tostring(row.nameRu or ""),
                weaponType = tostring(row.weaponType or ""),
                rarity = tostring(row.rarity or ""),
                modelAssetId = tostring(row.modelAssetId or ""),
            })
        end
    end
    table.sort(rows, function(left, right)
        if left.weaponType == right.weaponType then
            return left.nameEn < right.nameEn
        end
        return left.weaponType < right.weaponType
    end)
    return rows
end

function WeaponEquipService.EquipStartup(character: Model)
    local slug = tostring(WeaponRegistry.activeWeaponSlug or "")
    character:SetAttribute("WeaponLoadoutSource", "startup")
    if slug == "" then
        WeaponEquipService.Unequip(character)
        return
    end
    local ok, reason = WeaponEquipService.Equip(character, slug)
    if not ok then
        warn("[game1][weapon] " .. tostring(reason))
    else
        print(("[game1][weapon] startup loadout equipped %s"):format(slug))
    end
end

return table.freeze(WeaponEquipService)
