-- Server-only HP restoration for player characters. One bounded scheduler for
-- all players; dead/reviving characters never regenerate.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Config = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("character"):WaitForChild("CharacterStatsConfig"))

local CharacterRegenerationService = {}
local started = false
local accumulator = 0
local STEP = 0.2

function CharacterRegenerationService.Start()
    if started then return end
    started = true
    RunService.Heartbeat:Connect(function(dt)
        accumulator += math.clamp(dt, 0, 0.5)
        if accumulator < STEP then return end
        local elapsed = accumulator
        accumulator = 0
        for _, player in ipairs(Players:GetPlayers()) do
            local character = player.Character
            if character and character.Parent
                and character:GetAttribute("LifeState") == "Alive"
                and character:GetAttribute("Damageable") == true then
                local maxHP = math.max(0, tonumber(character:GetAttribute("MaxHP")) or 0)
                local hp = math.clamp(tonumber(character:GetAttribute("HP")) or 0, 0, maxHP)
                if hp > 0 and hp < maxHP then
                    character:SetAttribute("HP", math.min(maxHP, hp + Config.RegenerationHPPerSecond * elapsed))
                end
            end
        end
    end)
end
return table.freeze(CharacterRegenerationService)
