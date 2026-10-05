local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CharacterRegistry = require(CharacterShared:WaitForChild("CharacterRegistry"))

local CharacterService = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterService"))
local WeaponEquipService = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponEquipService"))

local TestLoadoutService = {}
local started = false

local function ensureRemoteFolder(): Folder
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if folder and folder:IsA("Folder") then
        return folder
    end
    if folder then
        folder:Destroy()
    end
    folder = Instance.new("Folder")
    folder.Name = "Game1Remotes"
    folder.Parent = ReplicatedStorage
    return folder
end

local function ensureRemoteFunction(parent: Instance, name: string): RemoteFunction
    local current = parent:FindFirstChild(name)
    if current and current:IsA("RemoteFunction") then
        return current
    end
    if current then
        current:Destroy()
    end
    local remote = Instance.new("RemoteFunction")
    remote.Name = name
    remote.Parent = parent
    return remote
end

local function characterLabel(row: any): string
    local displayName = tostring(row.displayName or row.id or "")
    local identity = string.format("%s / %s", tostring(row.race or "?"), tostring(row.gender or "?"))
    if displayName == "" then
        return identity
    end
    return displayName .. " · " .. identity
end

local function availableCharacters()
    local rows = {}
    for _, row in ipairs(CharacterService.ListAvailable()) do
        table.insert(rows, {
            id = tostring(row.id or ""),
            label = characterLabel(row),
            race = tostring(row.race or ""),
            gender = tostring(row.gender or ""),
        })
    end
    table.sort(rows, function(left, right)
        return left.label < right.label
    end)
    return rows
end

local function availableWeapons()
    local rows = {
        {
            slug = "",
            label = "Unarmed / Hands",
            weaponType = "hands",
            rarity = "",
            synthetic = true,
        },
    }
    for _, row in ipairs(WeaponEquipService.ListAvailable()) do
        local label = tostring(row.nameEn or row.slug)
        local russian = tostring(row.nameRu or "")
        if russian ~= "" then
            label ..= " / " .. russian
        end
        table.insert(rows, {
            slug = tostring(row.slug or ""),
            label = label,
            weaponType = tostring(row.weaponType or ""),
            rarity = tostring(row.rarity or ""),
            synthetic = false,
        })
    end
    return rows
end

local function buildCatalog(player: Player)
    local weapons = availableWeapons()
    local categoriesSeen = { hands = true }
    for _, row in ipairs(weapons) do
        categoriesSeen[tostring(row.weaponType or "hands")] = true
    end
    local categories = {}
    for category in pairs(categoriesSeen) do
        table.insert(categories, category)
    end
    table.sort(categories, function(left, right)
        if left == "hands" then
            return true
        end
        if right == "hands" then
            return false
        end
        return left < right
    end)

    local selectedArchetype = tostring(player:GetAttribute("SelectedCharacterArchetype") or "")
    if selectedArchetype == "" then
        selectedArchetype = tostring(CharacterRegistry.activeArchetypeId or "")
    end
    local selectedWeaponSlug = tostring(player:GetAttribute("SelectedWeaponSlug") or "")
    local character = player.Character
    if selectedWeaponSlug == "" and character then
        selectedWeaponSlug = tostring(character:GetAttribute("EquippedWeaponSlug") or "")
    end

    return {
        characters = availableCharacters(),
        categories = categories,
        categoryLabels = {
            hands = "Hands",
            ["1hs"] = "1HS",
            ["2hs"] = "2HS",
            bow = "Bow",
        },
        weapons = weapons,
        selectedArchetype = selectedArchetype,
        selectedWeaponSlug = selectedWeaponSlug,
    }
end

local function applyLoadout(player: Player, archetypeValue: any, weaponSlugValue: any)
    local archetype = string.lower(tostring(archetypeValue or ""))
    local weaponSlug = string.lower(tostring(weaponSlugValue or ""))
    if archetype == "" or not CharacterService.IsAvailable(archetype) then
        return { ok = false, error = "selected character archetype is not available" }
    end
    if weaponSlug ~= "" and not WeaponEquipService.GetAvailable(weaponSlug) then
        return { ok = false, error = "selected weapon is not registered" }
    end

    player:SetAttribute("SelectedWeaponSlug", weaponSlug)
    local character = CharacterService.Respawn(player, archetype)
    if not character then
        return { ok = false, error = "failed to spawn selected character archetype" }
    end

    local equipped = true
    local equipError = nil
    if weaponSlug == "" then
        WeaponEquipService.Unequip(character)
    else
        equipped, equipError = WeaponEquipService.Equip(character, weaponSlug)
    end
    if not equipped then
        return { ok = false, error = equipError or "failed to equip selected weapon" }
    end

    character:SetAttribute("WeaponLoadoutSource", "studio-test")
    player:SetAttribute("Game1TestLoadoutActive", true)
    return {
        ok = true,
        archetype = archetype,
        weaponSlug = weaponSlug,
        weaponType = tostring(character:GetAttribute("EquippedWeaponType") or "hands"),
        animationSet = tostring(character:GetAttribute("AnimationWeaponSet") or "hands"),
    }
end

local function bindPlayer(player: Player)
    player.CharacterAdded:Connect(function(character)
        task.defer(function()
            if not RunService:IsStudio() or player.Parent ~= Players or player.Character ~= character then
                return
            end
            if player:GetAttribute("Game1TestLoadoutActive") ~= true then
                return
            end
            local weaponSlug = string.lower(tostring(player:GetAttribute("SelectedWeaponSlug") or ""))
            if weaponSlug == "" then
                WeaponEquipService.Unequip(character)
                character:SetAttribute("WeaponLoadoutSource", "studio-test")
                return
            end
            local ok, reason = WeaponEquipService.Equip(character, weaponSlug)
            if ok then
                character:SetAttribute("WeaponLoadoutSource", "studio-test")
            else
                warn("[game1][test-loadout] " .. tostring(reason))
            end
        end)
    end)
end

function TestLoadoutService.Start()
    if started or not RunService:IsStudio() then
        return
    end
    started = true

    local remotes = ensureRemoteFolder()
    local catalog = ensureRemoteFunction(remotes, "GetTestLoadoutCatalog")
    local apply = ensureRemoteFunction(remotes, "ApplyTestLoadout")
    catalog.OnServerInvoke = buildCatalog
    apply.OnServerInvoke = applyLoadout

    Players.PlayerAdded:Connect(bindPlayer)
    for _, player in ipairs(Players:GetPlayers()) do
        bindPlayer(player)
    end
end

return table.freeze(TestLoadoutService)
