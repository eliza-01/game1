--!strict
-- Server-only XP/gold progression. Existing profile owns persistence; no reward remotes.
local Players = game:GetService("Players")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Profiles = require(script.Parent:WaitForChild("CharacterCreationProfileStore"))
local View = require(script.Parent:WaitForChild("CharacterProgressionView"))
local Loadout = require(script.Parent.Parent:WaitForChild("dev"):WaitForChild("GameplayTestLoadout"))
local DamageSignals = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("ActorDamageSignals"))
local Service = {}
local started = false
local function values(player: Player): (number, number)
    local record = Profiles.Get(player)
    if record then return Balance.NormalizeXP(record.xp), Balance.NormalizeGold(record.gold) end
    return Balance.NormalizeXP(player:GetAttribute("CharacterXP")), Balance.NormalizeGold(player:GetAttribute("CharacterGold"))
end
local function publish(player: Player, character: Model?, xp: number, gold: number)
    local level = Balance.LevelForXP(xp)
    player:SetAttribute("CharacterXP", xp)
    player:SetAttribute("CharacterGold", gold)
    player:SetAttribute("CharacterLevel", level)
    if character then View.Publish(character, xp, gold) end
end
function Service.LevelForPlayer(player: Player): number
    local xp = values(player)
    return Balance.LevelForXP(xp)
end
function Service.Attach(player: Player, character: Model)
    if Loadout.Get(player) then return end -- GP owns the transient projection
    local xp, gold = values(player)
    publish(player, character, xp, gold)
end
function Service.Start()
    if started then return end
    started = true
    DamageSignals.Event:Connect(function(attacker: Model?, target: Model, _attempted: number, applied: number, killed: boolean)
        if not killed or applied <= 0 or not attacker or target:GetAttribute("Game1MonsterRuntime") ~= true then return end
        local player = Players:GetPlayerFromCharacter(attacker)
        if not player or player.Character ~= attacker then return end
        if attacker:GetAttribute("Game1GameplayTestOwner") or target:GetAttribute("Game1GameplayTestOwner") then
            Loadout.Reward(player, attacker, target)
            return
        end
        local xp, gold = values(player)
        xp = Balance.NormalizeXP(xp + Balance.NormalizeXP(target:GetAttribute("RewardXP")))
        gold = Balance.NormalizeGold(gold + Balance.NormalizeGold(target:GetAttribute("RewardGold")))
        local record = Profiles.Get(player)
        if record then record.xp = xp; record.gold = gold end
        publish(player, attacker, xp, gold)
    end)
end
return table.freeze(Service)
