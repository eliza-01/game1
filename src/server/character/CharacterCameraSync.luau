--!strict
-- One-shot presentation notification after an authoritative teleport.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Heading = require(Shared:WaitForChild("character"):WaitForChild("CharacterCameraHeading"))

local Sync = {}
local remote: RemoteEvent? = nil

function Sync.Start(remotes: Instance)
    local existing = remotes:FindFirstChild(Heading.RemoteName)
    if existing then
        if not existing:IsA("RemoteEvent") then
            warn("[game1][camera] invalid camera alignment remote")
            return
        end
        remote = existing
    else
        local event = Instance.new("RemoteEvent")
        event.Name = Heading.RemoteName
        event.Parent = remotes
        remote = event
    end
end

function Sync.Align(player: Player, character: Model, targetFrame: CFrame)
    if player.Character ~= character then return end
    local event = remote
    if not event then
        warn("[game1][camera] camera alignment remote unavailable")
        return
    end
    event:FireClient(player, character, targetFrame.LookVector)
end

return table.freeze(Sync)
