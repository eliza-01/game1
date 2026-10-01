local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Config = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("CharacterStatsConfig"))
local Service = {}
function Service.Initialize(character: Model)
    local d = Config.Default
    character:SetAttribute("Level", d.Level)
    character:SetAttribute("MaxHP", d.MaxHP)
    character:SetAttribute("HP", d.MaxHP)
    character:SetAttribute("Damage", d.Damage)
    character:SetAttribute("Defense", d.Defense)
    character:SetAttribute("Damageable", true)
    character:SetAttribute("LifeState", "Alive")
end
return Service
