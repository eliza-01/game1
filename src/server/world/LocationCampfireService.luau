--!strict
-- Published Location placements: concrete campfire_01 Bones only. Fireplace
-- state is shared with House, while placement discovery stays in its domain.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local RunService = game:GetService("RunService")
local Environment = require(script.Parent:WaitForChild("EnvironmentAssetService"))
local Fireplace = require(script.Parent:WaitForChild("HouseFireplaceService"))
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CampfireContract = require(Shared:WaitForChild("world"):WaitForChild("CampfireSocketContract"))
local HouseContract = require(Shared:WaitForChild("world"):WaitForChild("HouseSocketContract"))
local PublishedDebugAccess = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))

local Service = {}
type Entry = {
    socket: Attachment?,
    cookingSocket: Attachment?,
    primary: ProximityPrompt?,
    alternate: ProximityPrompt?,
    connections: {RBXScriptConnection},
    promptConnections: {RBXScriptConnection},
}
local registered: {[Model]: Entry} = {}
local bySocket: {[Attachment]: Model} = {}
local cooldown: {[Player]: number} = {}
local started = false

local function useRadius(player: Player): number
    if RunService:IsStudio() then
        local override = player:GetAttribute(CampfireContract.RadiusAttribute("fire_socket"))
        if typeof(override) == "number" then
            return math.clamp(override, HouseContract.MinDebugRadius, HouseContract.MaxDebugRadius)
        end
    end
    return CampfireContract.Fire.radius
end

local function aimRadius(player: Player): number
    if RunService:IsStudio() then
        local override = player:GetAttribute(CampfireContract.HoverRadiusAttribute("fire_socket"))
        if typeof(override) == "number" then
            return math.clamp(override, HouseContract.MinHoverRadius, HouseContract.MaxHoverRadius)
        end
    end
    return CampfireContract.Fire.hoverRadius
end

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
    if not root or (root.Position - socketFrame(socket).Position).Magnitude > useRadius(player) then return end
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
    item.MaxActivationDistance = CampfireContract.Fire.radius
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
    entry.cookingSocket = cooking
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
        entry.primary, entry.alternate, entry.socket, entry.cookingSocket = nil, nil, nil, nil
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
    entry = {socket = nil, cookingSocket = nil, primary = nil, alternate = nil, connections = {}, promptConnections = {}}
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

-- Studio debug reads the EXISTING Environment registration; it never scans
-- Workspace or invents sockets on unbound models.
function Service.GetDebugStatus(player: Player): any
    local nearest: Model? = nil
    local nearestEntry: Entry? = nil
    local shortest = math.huge
    local total, bound = 0, 0
    local root = SpatialRoot.Get(player)
    for model, entry in pairs(registered) do
        if model:IsDescendantOf(Workspace) then
            total += 1
            if entry.socket and entry.cookingSocket then bound += 1 end
            local pivot = if entry.socket then socketFrame(entry.socket).Position else model:GetPivot().Position
            local distance = if root then (pivot - root.Position).Magnitude else 0
            if distance < shortest then
                shortest, nearest, nearestEntry = distance, model, entry
            end
        end
    end
    local rows = {}
    for _, definition in ipairs(CampfireContract.Definitions) do
        local socket = if definition == CampfireContract.Fire then
            (if nearestEntry then nearestEntry.socket else nil)
            else (if nearestEntry then nearestEntry.cookingSocket else nil)
        table.insert(rows, {
            name = definition.name, role = definition.role, domain = "campfire",
            radius = if definition.interact then useRadius(player) else 0,
            hoverRadius = if definition.hoverRadius then aimRadius(player) else nil,
            found = socket ~= nil and socket:IsDescendantOf(Workspace),
            house = if nearest then nearest.Name else "", action = definition.action,
        })
    end
    return {sockets = rows, total = total, bound = bound}
end

function Service.SetDebugRadius(player: Player, name: any, value: any): any
    if not RunService:IsStudio() or not PublishedDebugAccess.ServerAllowed(player)
        or name ~= "fire_socket" or typeof(value) ~= "number" or value ~= value
        or value == math.huge or value == -math.huge then
        return {ok = false, error = "Studio only: invalid campfire USE radius"}
    end
    local radius = math.clamp(value, HouseContract.MinDebugRadius, HouseContract.MaxDebugRadius)
    player:SetAttribute(CampfireContract.RadiusAttribute("fire_socket"), radius)
    return {ok = true, radius = radius}
end

function Service.SetDebugHoverRadius(player: Player, name: any, value: any): any
    if not RunService:IsStudio() or not PublishedDebugAccess.ServerAllowed(player)
        or name ~= "fire_socket" or typeof(value) ~= "number" or value ~= value
        or value == math.huge or value == -math.huge then
        return {ok = false, error = "Studio only: invalid campfire AIM radius"}
    end
    local radius = math.clamp(value, HouseContract.MinHoverRadius, HouseContract.MaxHoverRadius)
    player:SetAttribute(CampfireContract.HoverRadiusAttribute("fire_socket"), radius)
    return {ok = true, hoverRadius = radius}
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
