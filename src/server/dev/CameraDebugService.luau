--!strict
-- Studio Play only: validate camera drafts from the owning client.
-- All authoring persistence is handled by the local Control Center, not the game.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local PublishedDebugAccess = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local HttpService = game:GetService("HttpService")

local Service = {}
local started = false
local lastDraft: {[Player]: number} = {}
local limits = {
    targetHeight = {0, 12}, distance = {4, 18}, pitchDegrees = {-65, 60},
    characterX = {0.2, 0.8}, characterY = {0.2, 0.8},
    cursorX = {0.1, 0.9}, cursorY = {0.1, 0.9},
    mobileLookSpeed = {0.25, 4},
}

local function validate(values: any): {[string]: number}?
    if type(values) ~= "table" then return nil end
    local draft = {}
    for key, bounds in limits do
        local value = values[key]
        if type(value) ~= "number" or value ~= value or value == math.huge or value == -math.huge
            or value < bounds[1] or value > bounds[2] then return nil end
        draft[key] = value
    end
    return draft
end

function Service.Start()
    if started or not PublishedDebugAccess.ServerEnabled() then return end
    started = true
    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not remotes then
        remotes = Instance.new("Folder")
        remotes.Name = "Game1Remotes"
        remotes.Parent = ReplicatedStorage
    end
    local event = remotes:FindFirstChild("CameraDebugChanged")
    if not event then
        event = Instance.new("RemoteEvent")
        event.Name = "CameraDebugChanged"
        event.Parent = remotes
    end
    if not event:IsA("RemoteEvent") then
        warn("[game1][camera] CameraDebugChanged name collision")
        return
    end
    local folder = ReplicatedStorage:FindFirstChild("Game1CameraDebug")
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = "Game1CameraDebug"
        folder.Parent = ReplicatedStorage
    end
    event.OnServerEvent:Connect(function(player: Player, values: any)
    if not PublishedDebugAccess.ServerAllowed(player) then return end
        local now = os.clock()
        if now - (lastDraft[player] or -100) < 0.12 then return end
        local draft = validate(values)
        if not draft then return end
        lastDraft[player] = now
        -- Plugin reads this replicated Studio-only transport; no DataStore writes.
        folder:SetAttribute("Payload", HttpService:JSONEncode(draft))
        folder:SetAttribute("ChangedBy", player.UserId)
    end)
    game:GetService("Players").PlayerRemoving:Connect(function(player: Player)
        lastDraft[player] = nil
    end)
end

return table.freeze(Service)
