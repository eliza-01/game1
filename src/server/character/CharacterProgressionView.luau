--!strict
-- Shared server-side XP projection for persistent and transient progression.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Stats = require(script.Parent:WaitForChild("CharacterStatsService"))
local View = {}
function View.Publish(character: Model, xp: number, gold: number)
    local level = Balance.LevelForXP(xp)
    character:SetAttribute("XP", xp)
    character:SetAttribute("Gold", gold)
    character:SetAttribute("XPIntoLevel", xp - Balance.Threshold(level))
    character:SetAttribute("XPNext", Balance.Level(level).xpNext)
    if character:GetAttribute("Level") ~= level then Stats.SetProgressionLevel(character, level) end
end
return table.freeze(View)
