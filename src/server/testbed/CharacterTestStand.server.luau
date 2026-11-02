--!strict
-- Studio Play only: binds pre-authored ProximityPrompts under test stands.
-- Does nothing in published servers. Single folder watcher, no polling.
local RunService = game:GetService("RunService")
if not RunService:IsStudio() then return end

local Workspace = game:GetService("Workspace")
local Playback = require(script.Parent:WaitForChild("CharacterTestStandPlayback"))
local FOLDER_NAME = "Game1CharacterTestStands"
local active: {[Model]: () -> ()} = {}

local function attach(stand: Instance)
    if not stand:IsA("Model") or stand:GetAttribute("Game1CharacterTestStand") ~= true then return end
    if active[stand] then return end
    local anchor = stand:FindFirstChild("TestStandInteractionAnchor")
    local prompt = anchor and anchor:FindFirstChild("Game1NextAnimation")
    if not prompt or not prompt:IsA("ProximityPrompt")
        or prompt:GetAttribute("Game1CharacterTestStandPrompt") ~= true then return end
    active[stand] = Playback.Bind(stand, prompt)
end

local function detach(stand: Instance)
    if not stand:IsA("Model") then return end
    local dispose = active[stand]
    if dispose then active[stand] = nil; dispose() end
end

local watching: RBXScriptConnection? = nil
local function bindFolder(folder: Instance)
    if not folder:IsA("Folder") or folder.Name ~= FOLDER_NAME then return end
    if watching then watching:Disconnect() end
    for _, child in ipairs(folder:GetChildren()) do attach(child) end
    watching = folder.ChildAdded:Connect(attach)
    folder.ChildRemoved:Connect(detach)
end

local existing = Workspace:FindFirstChild(FOLDER_NAME)
if existing then bindFolder(existing) end
Workspace.ChildAdded:Connect(bindFolder)
print("[game1][character-stand] Studio Play E animation bench ready")
