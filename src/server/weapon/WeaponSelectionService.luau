--!strict
-- Runtime Playtest weapon chooser. Uses the same authoritative equip solver as
-- Test Loadout, without exposing character respawn/debug remotes to live players.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Config = require(Shared:WaitForChild("weapon"):WaitForChild("WeaponSelectionConfig"))
local Access = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local WeaponEquipService = require(script.Parent:WaitForChild("WeaponEquipService"))

local Service = {}
local started = false
local lastChange: {[Player]: number} = {}

local function remote(parent: Instance, name: string): RemoteFunction
    local existing = parent:FindFirstChild(name)
    if existing then
        assert(existing:IsA("RemoteFunction"), "invalid weapon selection remote: " .. name)
        return existing
    end
    local created = Instance.new("RemoteFunction")
    created.Name = name
    created.Parent = parent
    return created
end

local function catalogFor(player: Player)
    if not Access.ServerAllowed(player) then return {enabled = false, weapons = {}} end
    if not Config.Enabled then return { enabled = false, weapons = {} } end
    local character = player.Character
    local rows = {
        { slug = "", label = "Без оружия", weaponType = "hands" },
    }
    for _, row in ipairs(WeaponEquipService.ListAvailable()) do
        -- The catalog is server-owned; never trust names/slugs sent from UI.
        local russian = tostring(row.nameRu or "")
        table.insert(rows, {
            slug = tostring(row.slug),
            label = if russian ~= "" then russian else tostring(row.nameEn),
            weaponType = tostring(row.weaponType or ""),
        })
    end
    return {
        enabled = true,
        weapons = rows,
        selectedWeaponSlug = tostring(character and character:GetAttribute("EquippedWeaponSlug") or ""),
    }
end

local function selectWeapon(player: Player, request: any)
    if not Access.ServerAllowed(player) then return {ok = false, error = "Developer debug access denied"} end
    if not Config.Enabled then return { ok = false, error = "Выбор оружия отключён" } end
    if typeof(request) ~= "string" or #request > 80 then
        return { ok = false, error = "Некорректный ID оружия" }
    end
    local now = os.clock()
    if now - (lastChange[player] or -math.huge) < Config.CooldownSeconds then
        return { ok = false, error = "Слишком частая смена оружия" }
    end
    lastChange[player] = now
    local character = player.Character
    if not character or character.Parent == nil or tostring(character:GetAttribute("LifeState") or "Alive") ~= "Alive" then
        return { ok = false, error = "Персонаж ещё не готов" }
    end
    local slug = string.lower(request)
    if slug ~= "" then
        local allowed = false
        for _, row in ipairs(WeaponEquipService.ListAvailable()) do
            if row.slug == slug then allowed = true; break end
        end
        if not allowed then return { ok = false, error = "Оружие не опубликовано" } end
    end
    local previous = tostring(character:GetAttribute("EquippedWeaponSlug") or "")
    local success, ok, reason = pcall(function()
        if slug == "" then
            WeaponEquipService.Unequip(character)
            return true, nil
        end
        return WeaponEquipService.Equip(character, slug)
    end)
    if not success or not ok then
        -- Equip() can clear the old weapon on failure. Restore it if possible.
        pcall(function()
            if previous ~= "" then
                WeaponEquipService.Equip(character, previous)
            else
                WeaponEquipService.Unequip(character)
            end
        end)
        return { ok = false, error = if success then tostring(reason or "Оружие недоступно")
            else "Не удалось применить оружие" }
    end
    player:SetAttribute("SelectedWeaponSlug", slug)
    player:SetAttribute("Game1PlaytestWeaponChosen", true)
    character:SetAttribute("WeaponLoadoutSource", "playtest-selector")
    return { ok = true, selectedWeaponSlug = slug }
end

function Service.Start()
    if started or not Config.Enabled then return end
    started = true
    local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
    remote(remotes, "GetWeaponSelectionCatalog").OnServerInvoke = catalogFor
    remote(remotes, "SelectWeapon").OnServerInvoke = selectWeapon
    Players.PlayerRemoving:Connect(function(player)
        lastChange[player] = nil
    end)
end

return table.freeze(Service)
