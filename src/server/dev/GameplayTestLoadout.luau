--!strict
-- Transient loadout, separate from CharacterCreationProfileStore.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Stats = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterStatsService"))
local Weapons = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponEquipService"))
local Appearance = require(script.Parent:WaitForChild("GameplayTestAppearance"))
local Healing = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterHealing"))
local Critical = require(Shared:WaitForChild("balance"):WaitForChild("CriticalStats"))
local Loadout = {}
local sessions: {[Player]: any} = {}

function Loadout.Origin(): CFrame
    local t = Balance.Test
    return CFrame.new(t.x, t.y, t.z) * CFrame.Angles(0, math.rad(t.yaw), 0)
end
function Loadout.Get(player: Player): any?
    return sessions[player]
end
function Loadout.Set(player: Player, selection: any?)
    sessions[player] = selection
    player:SetAttribute("Game1GameplayTestActive", selection ~= nil)
end
function Loadout.Validate(request: any): (any?, string?)
    if type(request) ~= "table" then return nil, "Invalid loadout" end
    local level, upgrade = request.level, request.upgrade
    local regen = if request.regen == nil then 0 else request.regen
    local vampiric = if request.vampiric == nil then 0 else request.vampiric
    local critPercent = if request.critPercent == nil then 0 else request.critPercent
    local critFlat = if request.critFlat == nil then 0 else request.critFlat
    local critMultiplier = if request.critMultiplier == nil then Balance.Rules.critMultiplier else request.critMultiplier
    local critValid, critReason = Critical.ValidateTest(critPercent, critFlat, critMultiplier)
    if not critValid then return nil, critReason end
    local valid, recoveryReason = Healing.ValidateTestRates(regen, vampiric)
    if not valid then return nil, recoveryReason end
    if type(level) ~= "number" or level < 1 or level > #Balance.Monsters or level % 1 ~= 0 then return nil, "Invalid player level" end
    if type(upgrade) ~= "number" or upgrade < 0 or upgrade > Balance.Rules.maxUpgrade or upgrade % 1 ~= 0 then return nil, "Invalid upgrade" end
    if type(request.weapon) ~= "string" or type(request.armor) ~= "string" then return nil, "Invalid equipment IDs" end
    local weapon = if request.weapon == "" then nil else Balance.Weapon(request.weapon)
    local armor = Balance.Armor(request.armor)
    if (request.weapon ~= "" and not weapon) or not armor then return nil, "Unknown equipment ID" end
    if weapon then
        local _, required = Balance.Grade.ForLevel(weapon.level)
        if level < required then return nil, "Weapon requires LVL " .. required end
    end
    if level < armor.level then return nil, "Armor requires LVL " .. armor.level end
    local slug, placeholder = nil, false
    if weapon then
        slug, placeholder = Weapons.TestModel(weapon.type)
        if not slug then return nil, "No synced model for " .. weapon.type end
    end
    return {level=level, weapon=weapon, armor=armor, upgrade=upgrade, slug=slug, placeholder=placeholder, regen=regen, vampiric=vampiric, critPercent=critPercent, critFlat=critFlat, critMultiplier=critMultiplier}, nil
end
local function applyRecovery(character: Model, selection: any)
    character:SetAttribute("GameplayTestRegen", selection.regen)
    character:SetAttribute("GameplayTestVampiric", selection.vampiric)
end
function Loadout.SetRecovery(player: Player, character: Model, regen: any, vampiric: any): (boolean, string?)
    local selection = sessions[player]
    if not selection or player.Character ~= character or character:GetAttribute("GameplayTestKind") ~= "player"
        or character:GetAttribute("Game1GameplayTestOwner") ~= player.UserId then return false, "Not in Gameplay Test" end
    local valid, reason = Healing.ValidateTestRates(regen, vampiric)
    if not valid then return false, reason end
    selection.regen = regen
    selection.vampiric = vampiric
    applyRecovery(character, selection)
    return true, nil
end
function Loadout.Mark(player: Player, character: Model)
    if sessions[player] then
        character:SetAttribute("Game1GameplayTestOwner", player.UserId)
        character:SetAttribute("GameplayTestKind", "player")
    end
end
function Loadout.Apply(player: Player, character: Model): (boolean, string?)
    local selection = sessions[player]
    if not selection or character:GetAttribute("GameplayTestKind") ~= "player" then return false, "Not in Gameplay Test" end
    applyRecovery(character, selection)
    Stats.SetProgressionLevel(character, selection.level)
    Stats.SetModifierSource(character, "gameplay-test-armor", {MaxHP=selection.armor.hp})
    Appearance.Tint(character, Balance.Grade.Color(selection.armor.level), true)
    local ok, reason = true, nil
    if selection.weapon then
        ok, reason = Weapons.Equip(character, selection.slug, selection.weapon.id, selection.upgrade)
        local model = character:FindFirstChild("EquippedWeapon")
        if ok and model then Appearance.Tint(model, Balance.Grade.Color(selection.weapon.level)) end
    else
        Weapons.Unequip(character)
    end
    -- Named source is replaced (never accumulated) on every Apply / Start / respawn.
    Stats.SetModifierSource(character, "gameplay-test-critical", {
        CritChancePercent=selection.critPercent,
        CritChanceFlat=selection.critFlat,
        CritMultiplier=selection.critMultiplier - Balance.Rules.critMultiplier,
    })
    character:SetAttribute("GameplayTestError", if ok then nil else tostring(reason))
    character:SetAttribute("GameplayTestArmorId", selection.armor.id)
    character:SetAttribute("GameplayTestUpgrade", selection.upgrade)
    character:SetAttribute("WeaponLoadoutSource", "gameplay-test")
    character:SetAttribute("HP", character:GetAttribute("MaxHP"))
    -- HUD reflects the selected level, not the persisted XP of another level.
    character:SetAttribute("XP", Balance.Threshold(selection.level))
    character:SetAttribute("XPIntoLevel", 0)
    character:SetAttribute("XPNext", Balance.Level(selection.level).xpNext)
    character:SetAttribute("Gold", 0)
    return ok, reason
end
return table.freeze(Loadout)
