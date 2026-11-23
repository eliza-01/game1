--!strict
-- Server authority for door interaction; visual Bone.Transform is client-only.
-- Uses EnvironmentAssetService placement callbacks instead of Workspace polls.
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Environment = require(script.Parent:WaitForChild("EnvironmentAssetService"))
local Options = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("GameOptionsRegistry"))
local SpatialRoot = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))

local Service = {}
local SLUG = "windmill_02"
local USE_RADIUS = if Options.socketRanges and Options.socketRanges.windmill
    and Options.socketRanges.windmill.windmill_door_handle_socket
    then Options.socketRanges.windmill.windmill_door_handle_socket.useRadius else 8
local DURATION = 0.55

type Entry = {
    hinge: Bone?,
    handle: Attachment?,
    door: MeshPart?,
    prompt: ProximityPrompt?,
    authoredCollision: boolean?,
    connections: {RBXScriptConnection},
    bindConnections: {RBXScriptConnection},
    pending: boolean,
    interact: ((Player) -> ())?,
}
local entries: {[Model]: Entry} = {}
local cooldowns: {[Player]: number} = {}
local byHandle: {[Attachment]: Model} = {}
local started = false

local function findUnique(model: Model, name: string, className: string): Instance?
    local match: Instance? = nil
    for _, descendant in model:GetDescendants() do
        if descendant.Name == name and descendant:IsA(className) then
            if match then return nil end
            match = descendant
        end
    end
    return match
end

local function clearBinding(entry: Entry)
    if entry.handle then byHandle[entry.handle] = nil end
    entry.interact = nil
    for _, connection in entry.bindConnections do connection:Disconnect() end
    table.clear(entry.bindConnections)
    if entry.prompt then entry.prompt:Destroy() end
    entry.prompt = nil
    entry.hinge = nil
    entry.handle = nil
    entry.door = nil
    entry.authoredCollision = nil
end

local function clear(model: Model)
    local entry = entries[model]
    if not entry then return end
    entries[model] = nil
    clearBinding(entry)
    for _, connection in entry.connections do connection:Disconnect() end
end

local function socketPosition(socket: Attachment): Vector3
    return if socket:IsA("Bone") then (socket :: Bone).TransformedWorldCFrame.Position else socket.WorldPosition
end

local function bind(model: Model, entry: Entry)
    clearBinding(entry)
    if not model:IsDescendantOf(Workspace) then return end
    local hinge = findUnique(model, "windmill_door_socket", "Bone")
    local handle = findUnique(model, "windmill_door_handle_socket", "Attachment")
    local door = findUnique(model, "door", "MeshPart")
    if not hinge or not handle or not door then
        -- Never invent a handle/hinge or turn a generic click into a door.
        warn("[game1][windmill] " .. model:GetFullName()
            .. ": need unique windmill_door_socket (Bone), windmill_door_handle_socket (Attachment/Bone) and door (MeshPart)")
        return
    end
    entry.hinge = hinge :: Bone
    entry.handle = handle :: Attachment
    entry.door = door :: MeshPart
    byHandle[handle :: Attachment] = model
    local authored = model:GetAttribute("Game1WindmillDoorClosedCanCollide")
    if typeof(authored) ~= "boolean" then
        authored = (door :: MeshPart).CanCollide
        model:SetAttribute("Game1WindmillDoorClosedCanCollide", authored)
    end
    entry.authoredCollision = authored
    if model:GetAttribute("Game1WindmillDoorOpen") == nil then
        model:SetAttribute("Game1WindmillDoorOpen", false)
    end
    if model:GetAttribute("Game1WindmillDoorOpen") == true then
        local doorPart = door :: MeshPart
        doorPart.CanCollide = false
    end
    local prompt = Instance.new("ProximityPrompt")
    prompt.Name = "Game1HouseInteraction"
    prompt:SetAttribute("Game1SocketDomain", "windmill")
    prompt:SetAttribute("Game1SocketName", "windmill_door_handle_socket")
    prompt.Style = Enum.ProximityPromptStyle.Custom
    prompt.ActionText = "Открыть дверь"
    prompt.ObjectText = "Мельница"
    prompt.KeyboardKeyCode = Enum.KeyCode.F
    prompt.MaxActivationDistance = USE_RADIUS
    prompt.HoldDuration = 0
    prompt.RequiresLineOfSight = false
    prompt.Exclusivity = Enum.ProximityPromptExclusivity.OnePerButton
    prompt.Parent = handle
    entry.prompt = prompt
    local function interact(player: Player)
        if entries[model] ~= entry or entry.handle ~= handle or entry.prompt ~= prompt
            or not prompt.Enabled or not handle:IsDescendantOf(model) then return end
        local root = SpatialRoot.Get(player)
        if not root or (root.Position - socketPosition(handle :: Attachment)).Magnitude > USE_RADIUS then return end
        local current = os.clock()
        if current - (cooldowns[player] or 0) < DURATION + 0.15 then return end
        cooldowns[player] = current
        local open = model:GetAttribute("Game1WindmillDoorOpen") == true
        if not open then
            local doorPart = door :: MeshPart
            doorPart.CanCollide = false
        end
        model:SetAttribute("Game1WindmillDoorChangedAt", Workspace:GetServerTimeNow())
        model:SetAttribute("Game1WindmillDoorOpen", not open)
        prompt.ActionText = if open then "Открыть дверь" else "Закрыть дверь"
        if open then
            task.delay(DURATION, function()
                if entries[model] == entry and entry.door == door
                    and model:GetAttribute("Game1WindmillDoorOpen") ~= true then
                    local doorPart = door :: MeshPart
                    doorPart.CanCollide = entry.authoredCollision == true
                end
            end)
        end
    end
    entry.interact = interact
    table.insert(entry.bindConnections, prompt.Triggered:Connect(interact))
    table.insert(entry.bindConnections, handle.AncestryChanged:Connect(function()
        if handle:IsDescendantOf(model) then return end
        task.defer(function()
            if entries[model] == entry then bind(model, entry) end
        end)
    end))
end

local function scheduleBind(model: Model)
    local entry = entries[model]
    if not entry or entry.pending then return end
    entry.pending = true
    task.defer(function()
        if entries[model] ~= entry then return end
        entry.pending = false
        bind(model, entry)
    end)
end

local function observe(model: Model, definition: any?)
    if not definition or definition.slug ~= SLUG then
        clear(model)
        return
    end
    if entries[model] then return end
    local entry: Entry = {hinge=nil,handle=nil,door=nil,prompt=nil,authoredCollision=nil,
        connections={},bindConnections={},pending=false,interact=nil}
    entries[model] = entry
    table.insert(entry.connections, model.AncestryChanged:Connect(function()
        if not model:IsDescendantOf(Workspace) then clear(model) end
    end))
    table.insert(entry.connections, model.DescendantAdded:Connect(function(child)
        if child.Name == "door" or child.Name == "windmill_door_socket"
            or child.Name == "windmill_door_handle_socket" then scheduleBind(model) end
    end))
    table.insert(entry.connections, model.DescendantRemoving:Connect(function(child)
        if child.Name == "door" or child.Name == "windmill_door_socket"
            or child.Name == "windmill_door_handle_socket" then scheduleBind(model) end
    end))
    bind(model, entry)
end

function Service.Start()
    if started then return end
    started = true
    local remotes = game:GetService("ReplicatedStorage"):WaitForChild("Game1Remotes")
    local remote = remotes:FindFirstChild("WindmillSocketInteract")
    if not remote then
        remote = Instance.new("RemoteEvent")
        remote.Name = "WindmillSocketInteract"
        remote.Parent = remotes
    end
    if remote:IsA("RemoteEvent") then
        remote.OnServerEvent:Connect(function(player: Player, socket: any, key: any)
            if key ~= "F" or typeof(socket) ~= "Instance" or not socket:IsA("Attachment") then return end
            local model = byHandle[socket]
            local entry = model and entries[model]
            if entry and entry.handle == socket and entry.interact then entry.interact(player) end
        end)
    end
    Environment.Observe(observe)
    Players.PlayerRemoving:Connect(function(player)
        cooldowns[player] = nil
    end)
end

return table.freeze(Service)
