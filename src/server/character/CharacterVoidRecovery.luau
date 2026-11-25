-- Server-owned fallback for falling off the map. No client teleport or respawn remote.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Recovery = {}
local records = {}
local started = false
local CHECK_INTERVAL = 0.10
local TEST_DROP = 48
local DESTROY_MARGIN = 80

function Recovery.Watch(player: Player, character: Model, testFrame: CFrame?)
    records[player] = {character = character, testFrame = testFrame, nextAttempt = 0, busy = false}
end

function Recovery.Floor(destroyHeight: number, testFrame: CFrame?): number
    local floor = if destroyHeight == destroyHeight then destroyHeight + DESTROY_MARGIN else -1000
    if testFrame then
        -- Recover shortly below the deck, without waiting for the engine kill plane.
        floor = math.min(testFrame.Position.Y - 16, math.max(floor, testFrame.Position.Y - TEST_DROP))
    end
    return floor
end

function Recovery.Start(canRecover, restore)
    if started then return end
    started = true
    Players.PlayerRemoving:Connect(function(player) records[player] = nil end)
    local elapsed = 0
    RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < CHECK_INTERVAL then return end
        elapsed = 0
        for player, record in pairs(records) do
            local character = record.character
            local current = player.Character
            if record.busy or os.clock() < record.nextAttempt or not canRecover(player) then continue end
            -- Deliberate character replacement and ordinary combat deaths are not void falls.
            if current and current ~= character then continue end
            if character:GetAttribute("LifeState") ~= "Alive" then continue end
            local root = character:FindFirstChild("RootCollider")
            local missing = current == nil or not character.Parent or not root or not root:IsA("BasePart")
            if not missing and root.Position.Y > Recovery.Floor(Workspace.FallenPartsDestroyHeight, record.testFrame) then continue end
            record.busy = true
            record.nextAttempt = os.clock() + 2
            task.spawn(function()
                if records[player] == record and canRecover(player) and (player.Character == character or player.Character == nil) then
                    local ok, restored = pcall(restore, player, character)
                    if not ok or not restored then
                        warn("[game1][void-recovery] retry: " .. tostring(restored))
                    end
                end
                record.busy = false
            end)
        end
    end)
end
return table.freeze(Recovery)
