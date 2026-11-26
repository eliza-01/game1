--!strict
-- Transient loadout, separate from CharacterCreationProfileStore.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Stats = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterStatsService"))
local Weapons = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponEquipService"))
local Appearance = require(script.Parent:WaitForChild("GameplayTestAppearance"))
local Healing = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterHealing"))
local RunService = game:GetService("RunService")
local ProgressionView = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterProgressionView"))
local Critical = require(Shared:WaitForChild("balance"):WaitForChild("CriticalStats"))
local BufferConfig = require(Shared:WaitForChild("dev"):WaitForChild("GameplayBufferConfig"))
local Loadout = {}
local sessions: {[Player]: any} = {}

function Loadout.Origin(): CFrame
    local t = Balance.Test
    return CFrame.new(t.x, t.y + 1024, t.z) * CFrame.Angles(0, math.rad(t.yaw), 0)
end
function Loadout.Get(player: Player): any?
    return sessions[player]
end
function Loadout.Set(player: Player, selection: any?)
    if selection and selection.xp == nil then
        selection.xp = Balance.Threshold(selection.level)
        local previous = sessions[player]
        selection.gold = if previous then previous.gold else BufferConfig.StartingGold
    end
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
    if type(level) ~= "number" or level < 1 or level > Balance.MaxLevel or level % 1 ~= 0 then return nil, "Invalid player level" end
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
        if not slug then
            local required = if weapon.type == "bigsword" then "newbie_slayer_01" elseif weapon.type == "dualswords" then "newbie_sword_01" else weapon.type
            return nil, "No published/synced GP model: " .. required
        end
    end
    return {level=level, weapon=weapon, armor=armor, upgrade=upgrade, slug=slug, placeholder=placeholder, regen=regen, vampiric=vampiric, critPercent=critPercent, critFlat=critFlat, critMultiplier=critMultiplier}, nil
end
-- Stock tier from the canonical equipment catalogue; retain the selected type when available.
function Loadout.Stock(player: Player, level: number): (any?,string?)
    local current=sessions[player]
    local kind=if current and current.weapon then current.weapon.type else "sword"
    local weapon, fallback, armor=nil,nil,nil
    for _,row in ipairs(Balance.Weapons) do
        if row.level==level then
            if row.type==kind then weapon=row end
            if row.type=="sword" then fallback=row end
        end
    end
    for _,row in ipairs(Balance.Armors) do if row.level==level then armor=row; break end end
    weapon=weapon or fallback
    if not weapon or not armor then return nil,"Stock tier missing" end
    return Loadout.Validate({level=level,weapon=weapon.id,armor=armor.id,upgrade=0})
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
    Stats.SetProgressionLevel(character, Balance.LevelForXP(selection.xp))
    Stats.SetModifierSource(character, "gameplay-test-armor", {MaxHP=selection.armor.hp})
    Appearance.Tint(character, Balance.Grade.Color(selection.armor.level), true)
    local ok, reason = true, nil
    if selection.weapon then
        ok, reason = Weapons.Equip(character, selection.slug, selection.weapon.id, selection.upgrade)
        local model = character:FindFirstChild("EquippedWeapon")
        if ok and model then Appearance.Tint(model, Balance.Grade.Color(selection.weapon.level)) end
        local left = character:FindFirstChild("EquippedWeaponLeft")
        if ok and left then Appearance.Tint(left, Balance.Grade.Color(selection.weapon.level)) end
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
    if ok then
        local armorGrade=Balance.Grade.ForLevel(selection.armor.level)
        local weaponGrade=if selection.weapon then Balance.Grade.ForLevel(selection.weapon.level) else "—"
        local weaponType=if selection.weapon then selection.weapon.type else "hands"
        character:SetAttribute("GameplayTestEquipment",string.format("%s %s +%d · Armor %s",weaponGrade,weaponType,selection.upgrade,armorGrade))
    end
    character:SetAttribute("GameplayTestArmorId", selection.armor.id)
    character:SetAttribute("GameplayTestUpgrade", selection.upgrade)
    character:SetAttribute("WeaponLoadoutSource", "gameplay-test")
    character:SetAttribute("HP", character:GetAttribute("MaxHP"))
    ProgressionView.Publish(character, selection.xp, selection.gold)
    return ok, reason
end
-- A synchronous grant commits payment only if the effect was actually applied.
-- Called under the GP dispatcher lock; no client-provided cost or balance.
function Loadout.PurchaseBuff(player: Player, character: Model, grant: ()->boolean): boolean
    local selection = sessions[player]
    if not RunService:IsStudio() or not selection or player.Character ~= character
        or character:GetAttribute("GameplayTestKind") ~= "player"
        or character:GetAttribute("Game1GameplayTestOwner") ~= player.UserId
        or selection.gold < BufferConfig.Price then return false end
    if not grant() then return false end
    selection.gold -= BufferConfig.Price
    character:SetAttribute("Gold", selection.gold)
    return true
end
-- Only normal map kills earn rewards; no group/Guided or Skilled farming.
function Loadout.Reward(player: Player, character: Model, target: Model)
    local selection = sessions[player]
    if not RunService:IsStudio() or not selection or player.Character ~= character
        or character:GetAttribute("GameplayTestKind") ~= "player"
        or character:GetAttribute("Game1GameplayTestOwner") ~= player.UserId
        or target:GetAttribute("Game1GameplayTestOwner") ~= player.UserId
        or target:GetAttribute("GameplayTestKind") ~= "zone"
        or character:GetAttribute("GameplayGuideTrial") == true then return end
    local row = Balance.Monster(tostring(target:GetAttribute("MonsterBalanceId") or ""))
    if not row or row.skills then return end
    selection.xp = Balance.NormalizeXP(selection.xp + Balance.NormalizeXP(target:GetAttribute("RewardXP")))
    selection.gold = Balance.NormalizeGold(selection.gold + Balance.NormalizeGold(target:GetAttribute("RewardGold")))
    selection.level = Balance.LevelForXP(selection.xp)
    ProgressionView.Publish(character, selection.xp, selection.gold, true)
end
return table.freeze(Loadout)
