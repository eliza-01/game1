--!strict
-- Local visualization of registered Windmill 02 placements; no remote spam,
-- no server-side Bone.Transform (not network replicated), no per-frame scans.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Options = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("GameOptionsRegistry"))
local Rotor = require(script.Parent:WaitForChild("WindmillRotorVisual"))
local Door = require(script.Parent:WaitForChild("WindmillDoorVisual"))

local Controller = {}
local SLUG_ATTR = "Game1DecoAssetSlug"
local SLUG = "windmill_02"
local CULL_DISTANCE = 350

type Entry = {
    rotor: Rotor.State?,
    door: Door.State?,
    connections: {RBXScriptConnection},
    pending: boolean,
}
local entries: {[Model]: Entry} = {}
local started = false

local function dispose(model: Model)
    local entry = entries[model]
    if not entry then return end
    entries[model] = nil
    for _, connection in entry.connections do connection:Disconnect() end
    if entry.rotor then Rotor.Reset(entry.rotor) end
    if entry.door then Door.Reset(entry.door) end
end

local function rebind(model: Model)
    local entry = entries[model]
    if not entry then return end
    if entry.rotor then Rotor.Reset(entry.rotor) end
    if entry.door then Door.Reset(entry.door) end
    entry.rotor = Rotor.Bind(model)
    entry.door = Door.Bind(model)
end

local function scheduleRebind(model: Model)
    local entry = entries[model]
    if not entry or entry.pending then return end
    entry.pending = true
    task.defer(function()
        local current = entries[model]
        if current ~= entry then return end
        current.pending = false
        rebind(model)
    end)
end

local function discover(model: Model)
    if model:GetAttribute(SLUG_ATTR) ~= SLUG or not model:IsDescendantOf(Workspace) then return end
    if entries[model] then return end
    local entry: Entry = {rotor = nil, door = nil, connections = {}, pending = false}
    entries[model] = entry
    rebind(model)
    table.insert(entry.connections, model:GetAttributeChangedSignal(SLUG_ATTR):Connect(function()
        if model:GetAttribute(SLUG_ATTR) ~= SLUG then dispose(model) end
    end))
    table.insert(entry.connections, model.DescendantAdded:Connect(function(child)
        if child.Name == "blades" or child.Name == "fabric" or child.Name == "windmill_door_socket" then
            scheduleRebind(model)
        end
    end))
    table.insert(entry.connections, model.DescendantRemoving:Connect(function(child)
        if child.Name == "blades" or child.Name == "fabric" or child.Name == "windmill_door_socket" then
            scheduleRebind(model)
        end
    end))
    table.insert(entry.connections, model.AncestryChanged:Connect(function()
        if not model:IsDescendantOf(Workspace) then dispose(model) end
    end))
end

function Controller.Start()
    if started then return end
    started = true
    for _, object in Workspace:GetDescendants() do
        if object:IsA("Model") then discover(object) end
    end
    Workspace.DescendantAdded:Connect(function(object)
        if object:IsA("Model") then
            -- Instance placement and identity can arrive in separate frames.
            task.defer(function() discover(object) end)
        end
    end)
    local settings = Options.rotations and Options.rotations.windmill_02
    if not settings then
        warn("[game1][windmill] rotations config missing; motion disabled")
        return
    end
    RunService.RenderStepped:Connect(function()
        local camera = Workspace.CurrentCamera
        if not camera then return end
        local now = Workspace:GetServerTimeNow()
        for model, entry in pairs(entries) do
            local rotor = entry.rotor
            local door = entry.door
            local anchor = if rotor then rotor.pivot.Position else model:GetPivot().Position
            if (anchor - camera.CFrame.Position).Magnitude > CULL_DISTANCE then continue end
            if rotor and settings.enabled then
                Rotor.Update(rotor, now, settings.secondsPerRevolution)
            end
            if door then Door.Update(model, door, now) end
        end
    end)
end

return table.freeze(Controller)
