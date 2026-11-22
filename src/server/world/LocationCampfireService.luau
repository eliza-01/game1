--!strict
-- Published Location placements: concrete campfire_01 Bones only. Fireplace
-- state is shared with House, while placement discovery stays in its domain.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local Environment = require(script.Parent:WaitForChild("EnvironmentAssetService"))
local Fireplace = require(script.Parent:WaitForChild("HouseFireplaceService"))
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Config = require(Shared:WaitForChild("world"):WaitForChild("FireplaceMechanicsConfig"))
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))

local Service = {}
type Entry = {
    socket: Attachment?,
    primary: ProximityPrompt?,
    alternate: ProximityPrompt?,
    connections: {RBXScriptConnection},
    promptConnections: {RBXScriptConnection},
}
local registered: {[Model]: Entry} = {}
local bySocket: {[Attachment]: Model} = {}
local cooldown: {[Player]: number} = {}
local started = false

local function socketFrame(socket: Attachment): CFrame
    return if socket:IsA("Bone") then (socket :: Bone).TransformedWorldCFrame else socket.WorldCFrame
end

local function clear(model: Model)
    local entry = registered[model]
    if not entry then return end
    registered[model] = nil
    if entry.socket then bySocket[entry.socket] = nil end
    for _, c in ipairs(entry.connections) do c:Disconnect() end
    for _, c in ipairs(entry.promptConnections) do c:Disconnect() end
    Fireplace.Unregister(model)
    if entry.primary then entry.primary:Destroy() end
    if entry.alternate then entry.alternate:Destroy() end
end

local function handle(player: Player, socket: Attachment, key: string)
    if key ~= "E" and key ~= "F" then return end
    local model = bySocket[socket]
    local entry = model and registered[model]
    if not model or not entry or entry.socket ~= socket
        or not model:IsDescendantOf(Workspace) or not socket:IsDescendantOf(model) then return end
    local prompt = if key == "F" then entry.alternate else entry.primary
    if not prompt or not prompt.Enabled or prompt.Parent ~= socket then return end
    local root = SpatialRoot.Get(player)
    if not root or (root.Position - socketFrame(socket).Position).Magnitude > Config.CampfireInteractionRadius then return end
    local moment = os.clock()
    if moment - (cooldown[player] or 0) < 0.45 then return end
    cooldown[player] = moment
    Fireplace.Interact(model, player, key)
end

local function prompt(socket: Attachment, key: string): ProximityPrompt
    local item = Instance.new("ProximityPrompt")
    item.Name = if key == "E" then "Game1HouseInteraction" else "Game1HouseInteractionAlternate"
    item:SetAttribute("Game1SocketDomain", "campfire")
    item:SetAttribute("Game1SocketName", "fire_socket")
    item.KeyboardKeyCode = if key == "E" then Enum.KeyCode.E else Enum.KeyCode.F
    item.ActionText = if key == "E" then "Разжечь огонь" else "Убрать котел"
    item.ObjectText = ""
    item.HoldDuration = 0
    item.Style = Enum.ProximityPromptStyle.Custom
    item.Exclusivity = Enum.ProximityPromptExclusivity.OnePerButton
    item.MaxActivationDistance = Config.CampfireInteractionRadius
    item.RequiresLineOfSight = true
    item.Parent = socket
    return item
end

local function tryBind(model: Model, entry: Entry)
    if entry.socket or not model:IsDescendantOf(Workspace) then return end
    local fire: Attachment? = nil
    local cooking: Attachment? = nil
    local fireCount, cookingCount = 0, 0
    for _, child in ipairs(model:GetDescendants()) do
        if child:IsA("Attachment") then
            if child.Name == "fire_socket" then
                fireCount += 1
                fire = child
            elseif child.Name == "cooking_pot_01_socket" then
                cookingCount += 1
                cooking = child
            end
        end
    end
    -- Missing or ambiguous source sockets are not replaced by guessed positions.
    if fireCount ~= 1 or cookingCount ~= 1 or not fire or not cooking then return end
    entry.socket = fire
    bySocket[fire] = model
    Fireplace.RegisterCampfire(model, fire, cooking)
    local first = prompt(fire, "E")
    local second = prompt(fire, "F")
    entry.primary = first
    entry.alternate = second
    Fireplace.BindPrompts(model, fire, first, second)
    for _, p in {first, second} do
        table.insert(entry.promptConnections, p.Triggered:Connect(function(player)
            handle(player, fire :: Attachment, p.KeyboardKeyCode.Name)
        end))
    end
    -- Studio replacement can swap the authored rig without changing the
    -- Location slug. Drop only this binding, then re-resolve real Bones.
    table.insert(entry.promptConnections, fire.AncestryChanged:Connect(function()
        if fire:IsDescendantOf(model) then return end
        bySocket[fire] = nil
        Fireplace.Unregister(model)
        for _, c in ipairs(entry.promptConnections) do c:Disconnect() end
        table.clear(entry.promptConnections)
        if entry.primary then entry.primary:Destroy() end
        if entry.alternate then entry.alternate:Destroy() end
        entry.primary, entry.alternate, entry.socket = nil, nil, nil
        task.defer(function()
            if registered[model] == entry then tryBind(model, entry) end
        end)
    end))
end

local function observe(model: Model, definition: any?)
    if not definition or definition.slug ~= "campfire_01" then
        clear(model)
        return
    end
    local entry = registered[model]
    if entry then
        tryBind(model, entry)
        return
    end
    entry = {socket = nil, primary = nil, alternate = nil, connections = {}, promptConnections = {}}
    registered[model] = entry
    table.insert(entry.connections, model.AncestryChanged:Connect(function()
        if not model:IsDescendantOf(Workspace) then clear(model) end
    end))
    table.insert(entry.connections, model.DescendantAdded:Connect(function(child)
        if child:IsA("Attachment") and (child.Name == "fire_socket" or child.Name == "cooking_pot_01_socket") then
            task.defer(function()
                local current = registered[model]
                if current then tryBind(model, current) end
            end)
        end
    end))
    tryBind(model, entry)
end

function Service.Start()
    if started then return end
    started = true
    local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
    local remote = remotes:FindFirstChild("CampfireSocketInteract")
    if not remote then
        remote = Instance.new("RemoteEvent")
        remote.Name = "CampfireSocketInteract"
        remote.Parent = remotes
    end
    if remote:IsA("RemoteEvent") then
        remote.OnServerEvent:Connect(function(player, socket: any, key: any)
            if typeof(socket) ~= "Instance" or not socket:IsA("Attachment")
                or typeof(key) ~= "string" then return end
            handle(player, socket, key)
        end)
    end
    Environment.Observe(observe)
    Players.PlayerRemoving:Connect(function(player) cooldown[player] = nil end)
end

return table.freeze(Service)
