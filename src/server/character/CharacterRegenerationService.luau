-- Server-only HP restoration for player characters. One bounded scheduler for
-- all players; dead/reviving characters never regenerate.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Config = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("character"):WaitForChild("CharacterStatsConfig"))

local Healing = require(script.Parent:WaitForChild("CharacterHealing"))

local CharacterRegenerationService = {}
local started = false
local accumulator = 0
local STEP = 1

function CharacterRegenerationService.Start()
    if started then return end
    started = true
    if not RunService:IsStudio() and Config.RegenerationHPPerSecond <= 0 then return end
    RunService.Heartbeat:Connect(function(dt)
        accumulator += math.clamp(dt, 0, 0.5)
        if accumulator < STEP then return end
        local elapsed = math.floor(accumulator / STEP) * STEP
        accumulator -= elapsed
        for _, player in ipairs(Players:GetPlayers()) do
            local character = player.Character
            if character then
                -- Guided reports remain comparable to the pre-M545 zero-regen baseline.
                local guided = player:GetAttribute("GameplayGuideActive") == true
                local rate = if guided then 0 else Config.RegenerationHPPerSecond
                    + Healing.TestRate(character, "GameplayTestRegen")
                    + math.max(0, tonumber(character:GetAttribute("BuffGain_life")) or 0)
                if rate > 0 then Healing.Restore(character, rate * elapsed) end
            end
        end
    end)
end
return table.freeze(CharacterRegenerationService)
