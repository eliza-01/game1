--!strict
-- Shared server-side XP projection for persistent and transient progression.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Stats = require(script.Parent:WaitForChild("CharacterStatsService"))
local Feedback = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("CombatFeedbackService"))
local View = {}
function View.Publish(character: Model, xp: number, gold: number, earned: boolean?)
    local previousLevel = tonumber(character:GetAttribute("Level")) or 1
    local previousHP = tonumber(character:GetAttribute("MaxHP")) or 0
    local previousATK = tonumber(character:GetAttribute("Damage")) or 0
    local level = Balance.LevelForXP(xp)
    character:SetAttribute("XP", xp)
    character:SetAttribute("Gold", gold)
    character:SetAttribute("XPIntoLevel", xp - Balance.Threshold(level))
    character:SetAttribute("XPNext", Balance.Level(level).xpNext)
    if character:GetAttribute("Level") ~= level then Stats.SetProgressionLevel(character, level) end
    if earned == true and level > previousLevel then
        Feedback.PublishLevelUp(character, level,
            (tonumber(character:GetAttribute("MaxHP")) or 0) - previousHP,
            (tonumber(character:GetAttribute("Damage")) or 0) - previousATK)
    end
end
return table.freeze(View)
