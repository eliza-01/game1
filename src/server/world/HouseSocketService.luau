--!strict
-- Runtime registry of managed, placed homes and their *actual* imported
-- spatial sockets. No fabricated socket positions, no per-frame Workspace scans.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Contract = require(Shared:WaitForChild("world"):WaitForChild("HouseSocketContract"))
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local SpawnOrientation = require(Shared:WaitForChild("world"):WaitForChild("HouseSpawnOrientation"))
local Door = require(script.Parent:WaitForChild("HouseDoorService"))
local Padlock = require(script.Parent:WaitForChild("HousePadlockService"))
local Elevator = require(script.Parent:WaitForChild("HouseElevatorService"))
local Effects = require(script.Parent:WaitForChild("HouseSocketEffects"))
local Discovery = require(script.Parent:WaitForChild("HouseSocketDiscovery"))

local Service = {}
type Entry = {sockets: {[string]: Attachment}, connections: {RBXScriptConnection}, generated: {Instance}, padlockPart: BasePart?}
local registered: {[Model]: Entry} = {}
local started = false
local cooldown: {[Player]: number} = {}
local feedback: RemoteEvent? = nil
local refreshQueued: {[Model]: boolean} = {}
local watchedRoots: {[Model]: {RBXScriptConnection}} = {}
-- A Studio debug request may arrive after a house was inserted by an authoring
-- plugin. Only that explicit request is allowed to rescan the whole Workspace.
local reconcileWorld: (() -> {[string]: number})? = nil

local function rootPosition(player: Player): Vector3?
    local root = SpatialRoot.Get(player)
    return if root then root.Position else nil
end

local function getFrame(socket: Attachment): CFrame
    if socket:IsA("Bone") then return socket.TransformedWorldCFrame end
    return socket.WorldCFrame
end

local function hoverRadiusFor(player: Player, name: string): number?
    local definition = Contract.Get(name)
    if not definition or not definition.hoverRadius then return nil end
    if RunService:IsStudio() then
        local override = player:GetAttribute(Contract.HoverRadiusAttribute(name))
        if typeof(override) == "number" then
            return math.clamp(override, Contract.MinHoverRadius, Contract.MaxHoverRadius)
        end
    end
    return definition.hoverRadius
end

local function radiusFor(player: Player, name: string): number
    local definition = Contract.Get(name)
    if not definition then return 0 end
    if RunService:IsStudio() then
        local override = player:GetAttribute(Contract.RadiusAttribute(name))
        if typeof(override) == "number" then
            return math.clamp(override, Contract.MinDebugRadius, Contract.MaxDebugRadius)
        end
    end
    return definition.radius
end

-- A lock belongs to a house, not to either door handle. All prompt states
-- are server-replicated; the client never decides whether a door is unlocked.
local function updateDoorPrompts(entry: Entry, house: Model)
    local door = house:FindFirstChild("DoorAssembly")
    local open = door ~= nil and door:GetAttribute("Game1DoorOpen") == true
    local moving = Door.IsMoving(house)
    local hasPadlock = entry.sockets["door_01_padlock_01_socket"] ~= nil
    local locked = Padlock.IsAttached(house, hasPadlock)
    local canAttach = door ~= nil and door:IsA("Model")
        and Padlock.CanAttach(house, hasPadlock, open, moving)
    local action = if open then "Закрыть дверь" else "Открыть дверь"
    -- Both handles share the same two-action panel when the door is shut and
    -- unlocked. F must never be enabled during opening/closing animation.
    for _, name in {"door_01_handle_inside_socket", "door_01_handle_outside_socket"} do
        local socket = entry.sockets[name]
        local primary = socket and socket:FindFirstChild("Game1HouseInteraction")
        if primary and primary:IsA("ProximityPrompt") then
            primary.ActionText = action
            primary.Enabled = not locked
        end
        local alternate = socket and socket:FindFirstChild("Game1HouseInteractionAlternate")
        if alternate and alternate:IsA("ProximityPrompt") then
            alternate.ActionText = "Навесить замок · ключ"
            alternate.Enabled = canAttach
        end
    end
    local socket = entry.sockets["door_01_padlock_01_socket"]
    local prompt = socket and socket:FindFirstChild("Game1HouseInteraction")
    if prompt and prompt:IsA("ProximityPrompt") then
        prompt.ActionText = "Снять замок · ключ"
        prompt.Enabled = locked -- Re-attach only through F at either handle.
    end
    local part = entry.padlockPart
    if part then
        part.Transparency = if locked then 0.4 else 1
    end
end

local function handleInteraction(house: Model, name: string, player: Player, key: string)
    local entry = registered[house]
    local socket = entry and entry.sockets[name]
    local definition = Contract.Get(name)
    if not entry or not socket or not socket:IsDescendantOf(house) or not definition or not definition.interact then return end
    if key ~= "E" and key ~= "F" then return end
    if definition.role ~= "elevator" and definition.role ~= "door" and key ~= "E" then return end
    -- Check that the requested key is actually offered for this socket.
    -- Includes F only on offered elevator routes or unlocked door handles.
    if definition.role == "elevator" then
        local offered = false
        for _, option in Elevator.Options(entry.sockets, name) do
            if option.key == key then offered = true; break end
        end
        if not offered then return end
    elseif definition.role == "door" then
        local hasPadlock = entry.sockets["door_01_padlock_01_socket"] ~= nil
        if Padlock.IsAttached(house, hasPadlock) then return end
        if key == "F" then
            local door = house:FindFirstChild("DoorAssembly")
            if not door or not Padlock.CanAttach(house, hasPadlock,
                door:GetAttribute("Game1DoorOpen") == true, Door.IsMoving(house)) then return end
        end
    elseif definition.role == "padlock" then
        local door = house:FindFirstChild("DoorAssembly")
        if not Padlock.IsAttached(house, true) and (not door
            or door:GetAttribute("Game1DoorOpen") == true
            or Door.IsMoving(house)) then return end
    end
    local pos = rootPosition(player)
    -- Any AIM-enabled socket uses the exact USE radius; legacy +2 remains
    -- for door/padlock prompts, which do not have an AIM region.
    local allowedDistance = radiusFor(player, name) + (if definition.hoverRadius then 0 else 2)
    if not pos or (pos - getFrame(socket).Position).Magnitude > allowedDistance then return end
    local now = os.clock()
    if now - (cooldown[player] or 0) < 0.45 then return end
    cooldown[player] = now
    if definition.role == "door" and key == "F" then
        local door = house:FindFirstChild("DoorAssembly")
        local open = door ~= nil and door:GetAttribute("Game1DoorOpen") == true
        local _ok, reason = Padlock.Toggle(house, player, true, open, Door.IsMoving(house))
        if feedback then feedback:FireClient(player, reason) end
        updateDoorPrompts(entry, house)
    elseif definition.role == "door" then
        local ok, reason = Door.Toggle(house)
        if not ok then
            warn("[game1][house-socket] " .. reason)
            if feedback then
                feedback:FireClient(player, if RunService:IsStudio() then "Дверь недоступна: " .. reason else "Дверь недоступна")
            end
        else
            if feedback then
                feedback:FireClient(player, if (house:FindFirstChild("DoorAssembly") :: Model):GetAttribute("Game1DoorOpen") == true
                    then "Дверь открыта" else "Дверь закрыта")
            end
        end
        updateDoorPrompts(entry, house)
    elseif definition.role == "padlock" then
        local door = house:FindFirstChild("DoorAssembly")
        local doorOpen = door ~= nil and door:GetAttribute("Game1DoorOpen") == true
        local _ok, reason = Padlock.Toggle(house, player, true, doorOpen, Door.IsMoving(house))
        if feedback then feedback:FireClient(player, reason) end
        updateDoorPrompts(entry, house)
    elseif definition.role == "elevator" then
        local _ok, message = Elevator.Move(player, entry.sockets, name, key)
        if feedback then feedback:FireClient(player, message) end
    elseif definition.role == "chest" then
        if feedback then feedback:FireClient(player, "Сундук пока недоступен") end
    end
end

local function clear(house: Model)
    local entry = registered[house]
    if not entry then return end
    registered[house] = nil
    refreshQueued[house] = nil
    Door.Cleanup(house)
    for _, connection in entry.connections do connection:Disconnect() end
    for _, generated in entry.generated do generated:Destroy() end
end

local function register(house: Model)
    if registered[house] or not Discovery.IsHouse(house) then return end
    local entry: Entry = {sockets = {}, connections = {}, generated = {}, padlockPart = nil}
    registered[house] = entry
    local missing = {}
    local foundCount = 0
    -- One descendant pass per house, not one traversal for every socket.
    local socketByName: {[string]: Attachment} = {}
    local duplicateNames: {[string]: boolean} = {}
    for _, descendant in house:GetDescendants() do
        if descendant:IsA("Attachment") and Contract.Get(descendant.Name) then
            if socketByName[descendant.Name] then
                duplicateNames[descendant.Name] = true
            else
                socketByName[descendant.Name] = descendant
            end
        end
    end
    -- Resolve every socket before creating interaction prompts: an elevator
    -- must see its destination floors even if the source sorts first.
    for _, definition in Contract.Definitions do
        local found = socketByName[definition.name]
        local duplicate = duplicateNames[definition.name] == true
        if duplicate or not found then
            if not definition.optional then
                table.insert(missing, definition.name .. (if duplicate then " (duplicate)" else " (missing)"))
            end
            continue
        end
        entry.sockets[definition.name] = found :: Attachment
        foundCount += 1
    end
    Padlock.Ensure(house, entry.sockets["door_01_padlock_01_socket"] ~= nil)

    local function createPrompt(socket: Attachment, definition: Contract.SocketDefinition, key: string, action: string)
        local prompt = Instance.new("ProximityPrompt")
        prompt.Name = if key == "F" then "Game1HouseInteractionAlternate" else "Game1HouseInteraction"
        prompt:SetAttribute("Game1HouseSocketName", definition.name)
        prompt:SetAttribute("Game1HouseSocketRadius", definition.radius)
        prompt.ActionText = action
        prompt.ObjectText = ""
        prompt.KeyboardKeyCode = if key == "F" then Enum.KeyCode.F else Enum.KeyCode.E
        prompt.HoldDuration = 0
        prompt.MaxActivationDistance = Contract.MaxDebugRadius -- client + server policy restricts per socket
        prompt.RequiresLineOfSight = true
        if RunService:IsStudio() then prompt.RequiresLineOfSight = false end
        prompt.Exclusivity = Enum.ProximityPromptExclusivity.OnePerButton
        prompt.Style = Enum.ProximityPromptStyle.Custom
        prompt.Parent = socket
        table.insert(entry.generated, prompt)
        table.insert(entry.connections, prompt.Triggered:Connect(function(player)
            handleInteraction(house, definition.name, player, key)
        end))
    end

    for _, definition in Contract.Definitions do
        local socket = entry.sockets[definition.name]
        if not socket then continue end
        if definition.interact then
            if definition.role == "elevator" then
                for _, option in Elevator.Options(entry.sockets, definition.name) do
                    createPrompt(socket, definition, option.key, option.action)
                end
            else
                createPrompt(socket, definition, "E", definition.action)
                if definition.role == "door" and entry.sockets["door_01_padlock_01_socket"] then
                    createPrompt(socket, definition, "F", "Навесить замок · ключ")
                end
            end
        end
        if definition.placeholder then
            local part = Effects.CreatePlaceholder(house, socket, definition.placeholder)
            if part then
                table.insert(entry.generated, part)
                if definition.role == "padlock" then entry.padlockPart = part end
            end
        elseif definition.role == "chimney" then
            table.insert(entry.generated, Effects.StartSmoke(socket))
        end
    end
    local door = house:FindFirstChild("DoorAssembly")
    if door and door:IsA("Model") then
        for _, attribute in {"Game1DoorOpen", "Game1DoorMoving"} do
            table.insert(entry.connections, door:GetAttributeChangedSignal(attribute):Connect(function()
                updateDoorPrompts(entry, house)
            end))
        end
    end
    table.insert(entry.connections, house.AncestryChanged:Connect(function()
        if not house:IsDescendantOf(Workspace) then clear(house) end
    end))
    table.insert(entry.connections, house:GetAttributeChangedSignal("Game1PadlockAttached"):Connect(function()
        updateDoorPrompts(entry, house)
    end))
    updateDoorPrompts(entry, house)
    if #missing > 0 then
        -- Honest diagnosis: unweighted root Bones may not survive Roblox import.
        house:SetAttribute("Game1RuntimeMissingSockets", table.concat(missing, ", "))
        if foundCount > 0 then
            warn("[game1][house-socket] " .. house.Name .. ": " .. table.concat(missing, ", "))
        end
    else
        house:SetAttribute("Game1RuntimeMissingSockets", "")
    end
end

-- Studio refresh is explicit (HS REFRESH / TP), never a Heartbeat scan.
function Service.Reconcile(): {[string]: number}
    if not RunService:IsStudio() or not reconcileWorld then
        return {candidates = 0, repaired = 0, houses = 0, sockets = 0, prompts = 0}
    end
    return reconcileWorld()
end

function Service.FindNearest(player: Player, socketName: string): (Model?, Attachment?)
    if not Contract.Get(socketName) then return nil, nil end
    local pos = rootPosition(player)
    if not pos then return nil, nil end
    local nearest: Model? = nil
    local attachment: Attachment? = nil
    local distance = math.huge
    for house, entry in registered do
        local socket = entry.sockets[socketName]
        if socket and house.Parent then
            local d = (getFrame(socket).Position - pos).Magnitude
            if d < distance then
                distance = d
                nearest, attachment = house, socket
            end
        end
    end
    return nearest, attachment
end

function Service.GetDebugStatus(player: Player): {any}
    local rows = {}
    for _, definition in Contract.Definitions do
        local house, socket = Service.FindNearest(player, definition.name)
        table.insert(rows, {name = definition.name, role = definition.role,
            radius = radiusFor(player, definition.name),
            hoverRadius = hoverRadiusFor(player, definition.name), found = socket ~= nil,
            house = if house then house.Name else "", action = definition.action})
    end
    return rows
end

function Service.GetDebugKey(player: Player): boolean
    return Padlock.HasKey(player)
end

function Service.SetDebugKey(player: Player, owned: any): any
    if not RunService:IsStudio() or typeof(owned) ~= "boolean" then
        return {ok = false, error = "Studio only; key state must be boolean"}
    end
    Padlock.SetTestKey(player, owned)
    return {ok = true, owned = Padlock.HasKey(player)}
end

function Service.SetDebugRadius(player: Player, name: any, value: any): any
    if not RunService:IsStudio() or typeof(name) ~= "string" or not Contract.Get(name) then
        return {ok = false, error = "Unknown socket or not Studio"}
    end
    local radius = tonumber(value)
    if not radius or radius ~= radius then return {ok = false, error = "Radius must be numeric"} end
    radius = math.clamp(radius, Contract.MinDebugRadius, Contract.MaxDebugRadius)
    player:SetAttribute(Contract.RadiusAttribute(name), radius)
    return {ok = true, name = name, radius = radius}
end

function Service.SetDebugHoverRadius(player: Player, name: any, value: any): any
    local definition = if typeof(name) == "string" then Contract.Get(name) else nil
    if not RunService:IsStudio() or not definition or not definition.hoverRadius then
        return {ok = false, error = "Aim range is Studio-only and requires an AIM socket"}
    end
    local hoverRadius = tonumber(value)
    if not hoverRadius or hoverRadius ~= hoverRadius or hoverRadius == math.huge or hoverRadius == -math.huge then
        return {ok = false, error = "Aim radius must be finite"}
    end
    hoverRadius = math.clamp(hoverRadius, Contract.MinHoverRadius, Contract.MaxHoverRadius)
    player:SetAttribute(Contract.HoverRadiusAttribute(name), hoverRadius)
    return {ok = true, name = name, hoverRadius = hoverRadius}
end

function Service.TeleportDebug(player: Player, name: any): any
    if not RunService:IsStudio() or typeof(name) ~= "string" then
        return {ok = false, error = "Studio only"}
    end
    local definition = Contract.Get(name)
    if not definition or definition.role ~= "spawn" then
        return {ok = false, error = "Select a spawn socket"}
    end
    local diagnostic = Service.Reconcile()
    local house, socket = Service.FindNearest(player, name)
    if not house or not socket then
        return {ok = false, error = ("Spawn socket not found (houses %d; sockets %d; candidates %d)")
            :format(diagnostic.houses, diagnostic.sockets, diagnostic.candidates)}
    end
    local character = player.Character
    local root = SpatialRoot.Get(player)
    if not character or not root then return {ok = false, error = "Character not ready"} end
    -- Bone -Y is Blender Tail -> Head (spawn forward), not character up.
    -- Project the authored heading onto world XZ and keep the rig upright.
    local targetFrame = SpawnOrientation.Upright(getFrame(socket), socket:IsA("Bone"), 3)
    if not targetFrame then
        return {ok = false, error = "Spawn socket has no horizontal forward direction: " .. name}
    end
    character:PivotTo(targetFrame)
    local controller = character:FindFirstChildOfClass("ControllerManager")
    if controller then
        controller.MovingDirection = Vector3.zero
        controller.FacingDirection = targetFrame.LookVector
    end
    root.AssemblyLinearVelocity = Vector3.zero
    root.AssemblyAngularVelocity = Vector3.zero
    return {ok = true, house = house.Name, socket = name}
end

function Service.Start()
    if started then return end
    started = true
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = "Game1Remotes"
        folder.Parent = ReplicatedStorage
    end
    local remote = folder:FindFirstChild("HouseSocketFeedback")
    if not remote then
        remote = Instance.new("RemoteEvent")
        remote.Name = "HouseSocketFeedback"
        remote.Parent = folder
    end
    if remote:IsA("RemoteEvent") then feedback = remote end
    -- Custom characters do not use Roblox Humanoid proximity activation.
    -- Their client selects from server-authored prompts, then supplies only
    -- the replicated socket Instance. Ownership, reach and cooldown remain
    -- validated by handleInteraction on the server.
    local interactionRemote = folder:FindFirstChild("HouseSocketInteract")
    if not interactionRemote then
        interactionRemote = Instance.new("RemoteEvent")
        interactionRemote.Name = "HouseSocketInteract"
        interactionRemote.Parent = folder
    end
    if interactionRemote:IsA("RemoteEvent") then
        interactionRemote.OnServerEvent:Connect(function(player, socket: any, key: any)
            if typeof(socket) ~= "Instance" or not socket:IsA("Attachment")
                or (key ~= "E" and key ~= "F") then return end
            local house = Discovery.OwnerOf(socket)
            if not house then return end
            local entry = registered[house]
            if not entry or entry.sockets[socket.Name] ~= socket then return end
            handleInteraction(house, socket.Name, player, key)
        end)
    end
    local function safeRegister(house: Model)
        local ok, err = pcall(register, house)
        if not ok then
            -- A broken imported model must not prevent other houses from working.
            clear(house)
            warn("[game1][house-socket] registration failed " .. house:GetFullName() .. ": " .. tostring(err))
        end
    end

    local function scheduleRefresh(house: Model)
        if refreshQueued[house] then return end
        refreshQueued[house] = true
        task.defer(function()
            if not refreshQueued[house] then return end
            refreshQueued[house] = nil
            if registered[house] then clear(house) end
            if house:IsDescendantOf(Workspace) then safeRegister(house) end
        end)
    end

    local function watchRoot(house: Model)
        if watchedRoots[house] then return end
        local connections: {RBXScriptConnection} = {}
        watchedRoots[house] = connections
        -- Asset sync may assign the slug after parenting all of the geometry.
        table.insert(connections, house:GetAttributeChangedSignal("Game1RealEstateSlug"):Connect(function()
            scheduleRefresh(house)
        end))
        table.insert(connections, house:GetAttributeChangedSignal("Game1RealEstateTemplate"):Connect(function()
            scheduleRefresh(house)
        end))
        table.insert(connections, house.AncestryChanged:Connect(function()
            if not house:IsDescendantOf(Workspace) then
                for _, connection in connections do connection:Disconnect() end
                watchedRoots[house] = nil
                refreshQueued[house] = nil
                clear(house)
            end
        end))
    end

    local function needsRepair(house: Model, entry: Entry): boolean
        -- Real bones may become children of a previously registered shell.
        -- Compare the actual authoring sockets with the cached runtime map.
        for _, descendant in house:GetDescendants() do
            if descendant:IsA("Attachment") and Contract.Get(descendant.Name) then
                if entry.sockets[descendant.Name] ~= descendant then return true end
                local definition = Contract.Get(descendant.Name)
                if definition and definition.interact then
                    local options = if definition.role == "elevator" then Elevator.Options(entry.sockets, descendant.Name) else {}
                    local hasE = definition.role ~= "elevator"
                    local hasF = definition.role == "door"
                        and entry.sockets["door_01_padlock_01_socket"] ~= nil
                    for _, option in options do
                        if option.key == "E" then hasE = true end
                        if option.key == "F" then hasF = true end
                    end
                    if hasE and not descendant:FindFirstChild("Game1HouseInteraction") then return true end
                    if hasF and not descendant:FindFirstChild("Game1HouseInteractionAlternate") then return true end
                end
            end
        end
        for _, socket in entry.sockets do
            if not socket:IsDescendantOf(house) then return true end
        end
        return false
    end

    local function seeModel(model: Model)
        if not Discovery.IsPotentialHouseRoot(model) then return end
        watchRoot(model)
        if not registered[model] then
            safeRegister(model)
        end
    end

    local function snapshot(): {[string]: number}
        local houses, sockets, prompts = 0, 0, 0
        for _, entry in registered do
            houses += 1
            for name, socket in entry.sockets do
                sockets += 1
                local definition = Contract.Get(name)
                if definition and definition.interact then
                    if socket:FindFirstChild("Game1HouseInteraction") then prompts += 1 end
                    if socket:FindFirstChild("Game1HouseInteractionAlternate") then prompts += 1 end
                end
            end
        end
        return {houses = houses, sockets = sockets, prompts = prompts}
    end

    local function reconcile(): {[string]: number}
        local candidates, repaired, authored = 0, 0, 0
        for _, descendant in Workspace:GetDescendants() do
            if not descendant:IsA("Model") or not Discovery.IsPotentialHouseRoot(descendant) then continue end
            candidates += 1
            if Discovery.IsHouse(descendant) then
                for _, socket in descendant:GetDescendants() do
                    if socket:IsA("Attachment") and Contract.Get(socket.Name) then
                        authored += 1
                    end
                end
            end
            watchRoot(descendant)
            local entry = registered[descendant]
            if not entry or needsRepair(descendant, entry) then
                if entry then clear(descendant) end
                safeRegister(descendant)
                repaired += 1
            end
        end
        local result = snapshot()
        result.candidates = candidates
        result.repaired = repaired
        result.authored = authored
        return result
    end
    reconcileWorld = reconcile

    -- Initial snapshot, followed by model/socket events. No Heartbeat scans.
    local startup = reconcile()
    Workspace.DescendantAdded:Connect(function(descendant)
        if descendant:IsA("Model") then
            seeModel(descendant)
            -- HouseRig and DoorAssembly can be inserted before the root slug.
            local parent = descendant.Parent
            if parent and parent:IsA("Model") and Discovery.IsPotentialHouseRoot(parent) then
                watchRoot(parent)
                scheduleRefresh(parent)
            end
        elseif descendant:IsA("Attachment") and Contract.Get(descendant.Name) then
            local house = Discovery.OwnerOf(descendant)
            if house then
                watchRoot(house)
                scheduleRefresh(house)
            end
        end
    end)
    Workspace.DescendantRemoving:Connect(function(descendant)
        if descendant:IsA("Attachment") and Contract.Get(descendant.Name) then
            local house = Discovery.OwnerOf(descendant)
            if house then scheduleRefresh(house) end
        end
    end)
    Players.PlayerRemoving:Connect(function(player) cooldown[player] = nil end)
    print(("[game1][house-socket] ready · %d house(s) · %d socket(s) · %d prompt(s)")
        :format(startup.houses, startup.sockets, startup.prompts))
end

return table.freeze(Service)
