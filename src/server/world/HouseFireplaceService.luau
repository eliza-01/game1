--!strict
local AssetService = game:GetService("AssetService")
local InsertService = game:GetService("InsertService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local WorldShared = Shared:WaitForChild("world")
local SocketFacing = require(WorldShared:WaitForChild("SocketFacing"))
local Registry = require(WorldShared:WaitForChild("LocationAssetRegistry"))
local Config = require(WorldShared:WaitForChild("FireplaceMechanicsConfig"))

local Service = {}

type State = {
    house: Model,
    socket: Attachment,
    runtimeFolder: Folder,
    primaryPrompt: ProximityPrompt?,
    alternatePrompt: ProximityPrompt?,
    fuelStage: string,
    fuelEndsAt: number,
    fuelDuration: number,
    fuelRevision: number,
    fuelInstance: Instance?,
    fireAnchor: Attachment?,
    fire: Fire?,
    light: PointLight?,
    potInstance: Instance?,
    potSocket: Attachment?,
    steam: ParticleEmitter?,
    potState: string,
    cookEndsAt: number,
    cookDuration: number,
    cookRevision: number,
    cookOwner: Player?,
}

local states: {[Model]: State} = {}
local feedbackRemote: RemoteEvent? = nil
local prototypeCache: {[string]: Instance} = {}

local function getFrame(socket: Attachment): CFrame
    if socket:IsA("Bone") then return socket.TransformedWorldCFrame end
    return socket.WorldCFrame
end

local function promptRef(socket: Attachment, name: string): ProximityPrompt?
    local prompt = socket:FindFirstChild(name)
    return if prompt and prompt:IsA("ProximityPrompt") then prompt else nil
end

local function fireAnchor(state: State): Attachment
    local existing = state.fireAnchor
    if existing and existing.Parent then return existing end
    local anchor = Instance.new("Attachment")
    anchor.Name = "Game1FireplaceFireAnchor"
    anchor.Parent = state.socket
    state.fireAnchor = anchor
    return anchor
end

local function ensureFireVisual(state: State, enabled: boolean)
    local anchor = fireAnchor(state)
    local fire = state.fire
    if not fire then
        fire = Instance.new("Fire")
        fire.Name = "Game1FireplaceFlame"
        fire.Size = Config.Fire.Size
        fire.Heat = Config.Fire.Heat
        fire.TimeScale = Config.Fire.TimeScale
        fire.Color = Config.Fire.Primary
        fire.SecondaryColor = Config.Fire.Secondary
        fire.Parent = anchor
        state.fire = fire
    end
    fire.Enabled = enabled
    local light = state.light
    if not light then
        light = Instance.new("PointLight")
        light.Name = "Game1FireplaceLight"
        light.Brightness = Config.Light.Brightness
        light.Range = Config.Light.Range
        light.Color = Config.Light.Color
        light.Shadows = Config.Light.Shadows
        light.Enabled = Config.Light.Enabled
        light.Parent = anchor
        state.light = light
    end
    light.Enabled = enabled and Config.Light.Enabled
end

local function assetPrototype(slug: string): Instance?
    if prototypeCache[slug] then return prototypeCache[slug] end
    local definition = Registry.assets[slug]
    if type(definition) ~= "table" then return nil end
    local assetId = tonumber(definition.modelAssetId)
    if not assetId then return nil end
    local ok, loaded = pcall(InsertService.LoadAsset, InsertService, assetId)
    if not ok or not loaded then
        ok, loaded = pcall(AssetService.LoadAssetAsync, AssetService, assetId)
    end
    if not ok or not loaded or not loaded:IsA("Model") then
        warn("[game1][fireplace] load failed " .. slug .. ": " .. tostring(loaded))
        return nil
    end
    local root: Instance = loaded
    for _, descendant in ipairs(root:GetDescendants()) do
        if descendant:IsA("Script") or descendant:IsA("LocalScript") or descendant:IsA("ModuleScript") then
            descendant:Destroy()
        end
    end
    prototypeCache[slug] = root
    return root
end

local function worldTarget(socket: Attachment): CFrame
    local fromBone = socket:IsA("Bone")
    return SocketFacing.FullFrame(getFrame(socket), fromBone)
end

local function placeholder(slug: string, parent: Instance, frame: CFrame): BasePart
    local part = Instance.new("Part")
    part.Name = slug
    part.Size = if slug == "cooking_pot_01" then Vector3.new(1.5, 1, 1.5)
        elseif slug == "embers_01" then Vector3.new(1.3, 0.25, 1.3)
        else Vector3.new(1.4, 0.45, 1.1)
    part.Material = if slug == "embers_01" then Enum.Material.CrackedLava else Enum.Material.Wood
    part.Color = if slug == "embers_01" then Color3.fromRGB(201, 13, 13)
        elseif slug == "cooking_pot_01" then Color3.fromRGB(76, 79, 84)
        else Color3.fromRGB(117, 90, 81)
    part.Anchored = true
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = false
    part.CastShadow = false
    part.CFrame = frame
    part.Parent = parent
    return part
end

local function cloneAsset(slug: string, parent: Instance, socket: Attachment): (Instance, Attachment?)
    local frame = worldTarget(socket)
    local prototype = assetPrototype(slug)
    local clone = if prototype then prototype:Clone() else nil
    if not clone then
        return placeholder(slug, parent, frame), nil
    end
    clone.Name = slug
    for _, descendant in ipairs(clone:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
            descendant.CastShadow = true
            descendant.Massless = true
        end
    end
    clone.Parent = parent
    local foundSocket: Attachment? = nil
    if clone:IsA("Model") then
        clone:PivotTo(frame)
        local descendant = clone:FindFirstChild("cooking_pot_socket", true)
        if descendant and (descendant:IsA("Attachment") or descendant:IsA("Bone")) then
            foundSocket = descendant :: Attachment
        end
    elseif clone:IsA("BasePart") then
        clone.CFrame = frame
    end
    return clone, foundSocket
end

local function steamTarget(state: State): Attachment?
    local socket = state.potSocket
    if socket and socket.Parent then return socket end
    return state.socket
end

local function ensureSteam(state: State, enabled: boolean)
    local target = steamTarget(state)
    if not target then return end
    local steam = state.steam
    if not steam then
        steam = Instance.new("ParticleEmitter")
        steam.Name = "Game1CookingSteam"
        steam.Rate = Config.Steam.Rate
        steam.Lifetime = Config.Steam.Lifetime
        steam.Speed = Config.Steam.Speed
        steam.SpreadAngle = Config.Steam.SpreadAngle
        steam.Acceleration = Config.Steam.Acceleration
        steam.RotSpeed = NumberRange.new(-10, 10)
        steam.Rotation = NumberRange.new(0, 360)
        steam.Size = NumberSequence.new({
            NumberSequenceKeypoint.new(0, 0.35),
            NumberSequenceKeypoint.new(0.65, 0.85),
            NumberSequenceKeypoint.new(1, 1.1),
        })
        steam.Transparency = NumberSequence.new({
            NumberSequenceKeypoint.new(0, 0.35),
            NumberSequenceKeypoint.new(0.65, 0.55),
            NumberSequenceKeypoint.new(1, 1),
        })
        steam.Color = ColorSequence.new(Color3.fromRGB(220, 223, 227), Color3.fromRGB(246, 246, 246))
        steam.LightEmission = 0
        steam.Parent = target
        state.steam = steam
    end
    steam.Enabled = enabled
end

local function notify(player: Player?, payload: any)
    if player and feedbackRemote then
        feedbackRemote:FireClient(player, payload)
    end
end

local function now(): number
    return Workspace:GetServerTimeNow()
end

local function syncPromptState(state: State)
    local primary = state.primaryPrompt or promptRef(state.socket, "Game1HouseInteraction")
    local alternate = state.alternatePrompt or promptRef(state.socket, "Game1HouseInteractionAlternate")
    state.primaryPrompt, state.alternatePrompt = primary, alternate
    if primary then
        primary.Enabled = false
        if state.fuelStage == "empty" then
            if not state.potInstance then
                primary.ActionText = "Разжечь огонь"
                primary.Enabled = true
            elseif state.potState == "ready" then
                primary.ActionText = "Забрать блюдо"
                primary.Enabled = true
            else
                primary.ActionText = if state.potState == "cooking" then "Блюдо готовится" else "Камин"
                primary.Enabled = false
            end
        elseif state.fuelStage == "firewood" and not state.potInstance then
            primary.ActionText = "Поставить котел"
            primary.Enabled = true
        elseif state.potInstance then
            if state.potState == "idle" then
                primary.ActionText = "Добавить ингредиенты"
                primary.Enabled = true
            elseif state.potState == "ready" then
                primary.ActionText = "Забрать блюдо"
                primary.Enabled = true
            else
                primary.ActionText = "Блюдо готовится"
                primary.Enabled = false
            end
        else
            primary.ActionText = "Камин"
            primary.Enabled = false
        end
    end
    if alternate then
        alternate.ActionText = "Убрать котел"
        alternate.Enabled = state.potInstance ~= nil and state.potState == "idle"
    end
end

local function syncAttributes(state: State)
    local socket = state.socket
    socket:SetAttribute("Game1FireplaceFuelState", state.fuelStage)
    socket:SetAttribute("Game1FireplaceFuelEndsAt", state.fuelEndsAt)
    socket:SetAttribute("Game1FireplaceFuelDuration", state.fuelDuration)
    socket:SetAttribute("Game1FireplacePotPresent", state.potInstance ~= nil)
    socket:SetAttribute("Game1FireplaceCookState", state.potState)
    socket:SetAttribute("Game1FireplaceCookEndsAt", state.cookEndsAt)
    socket:SetAttribute("Game1FireplaceCookDuration", state.cookDuration)
    socket:SetAttribute("Game1FireplaceVisibleRadius", Config.ProgressVisibleRadius)
    syncPromptState(state)
    ensureSteam(state, state.potInstance ~= nil and state.fuelStage ~= "empty")
end

local function replaceFuel(state: State, slug: string?)
    if state.fuelInstance then
        state.fuelInstance:Destroy()
        state.fuelInstance = nil
    end
    if slug and slug ~= "" then
        state.fuelInstance = cloneAsset(slug, state.runtimeFolder, state.socket)
    end
end

local function transitionToEmpty(state: State, revision: number)
    if states[state.house] ~= state or state.fuelRevision ~= revision then return end
    state.fuelStage = "empty"
    state.fuelEndsAt = 0
    state.fuelDuration = 0
    replaceFuel(state, nil)
    ensureFireVisual(state, false)
    syncAttributes(state)
end

local function transitionToEmbers(state: State, revision: number)
    if states[state.house] ~= state or state.fuelRevision ~= revision then return end
    state.fuelStage = "embers"
    state.fuelDuration = Config.EmbersDurationSeconds
    state.fuelEndsAt = now() + Config.EmbersDurationSeconds
    replaceFuel(state, "embers_01")
    ensureFireVisual(state, false)
    syncAttributes(state)
    task.delay(Config.EmbersDurationSeconds, function()
        transitionToEmpty(state, revision)
    end)
end

local function startFire(state: State)
    state.fuelRevision += 1
    state.fuelStage = "firewood"
    state.fuelDuration = Config.FuelDurationSeconds
    state.fuelEndsAt = now() + Config.FuelDurationSeconds
    replaceFuel(state, "firewood_01")
    ensureFireVisual(state, true)
    syncAttributes(state)
    local revision = state.fuelRevision
    task.delay(Config.FuelDurationSeconds, function()
        transitionToEmbers(state, revision)
    end)
end

local function removePot(state: State)
    if state.potInstance then state.potInstance:Destroy() end
    state.potInstance = nil
    state.potSocket = nil
    if state.steam then state.steam:Destroy(); state.steam = nil end
    state.potState = "idle"
    state.cookEndsAt = 0
    state.cookDuration = 0
    state.cookOwner = nil
    syncAttributes(state)
end

local function placePot(state: State)
    local instance, potSocket = cloneAsset("cooking_pot_01", state.runtimeFolder, state.socket)
    state.potInstance = instance
    state.potSocket = potSocket
    state.potState = "idle"
    state.cookEndsAt = 0
    state.cookDuration = 0
    syncAttributes(state)
end

local function finishCooking(state: State, revision: number)
    if states[state.house] ~= state or state.cookRevision ~= revision then return end
    state.potState = "ready"
    state.cookEndsAt = 0
    state.cookDuration = 0
    syncAttributes(state)
    notify(state.cookOwner, {kind = "toast", text = "Блюдо готово"})
end

local function startCooking(state: State, player: Player)
    state.cookRevision += 1
    state.potState = "cooking"
    state.cookDuration = if state.fuelStage == "embers" then Config.CookingSecondsOnEmbers else Config.CookingSecondsOnFire
    state.cookEndsAt = now() + state.cookDuration
    state.cookOwner = player
    syncAttributes(state)
    local revision = state.cookRevision
    task.delay(state.cookDuration, function()
        finishCooking(state, revision)
    end)
end

function Service.SetFeedbackRemote(remote: RemoteEvent)
    feedbackRemote = remote
end

function Service.Register(house: Model, socket: Attachment, generated: {Instance}?)
    if states[house] then return end
    local folder = Instance.new("Folder")
    folder.Name = "Game1FireplaceRuntime"
    folder.Parent = house
    local state: State = {
        house = house,
        socket = socket,
        runtimeFolder = folder,
        primaryPrompt = nil,
        alternatePrompt = nil,
        fuelStage = "empty",
        fuelEndsAt = 0,
        fuelDuration = 0,
        fuelRevision = 0,
        fuelInstance = nil,
        fireAnchor = nil,
        fire = nil,
        light = nil,
        potInstance = nil,
        potSocket = nil,
        steam = nil,
        potState = "idle",
        cookEndsAt = 0,
        cookDuration = 0,
        cookRevision = 0,
        cookOwner = nil,
    }
    states[house] = state
    if generated then table.insert(generated, folder) end
    syncAttributes(state)
end

function Service.BindPrompts(house: Model, socket: Attachment, primary: ProximityPrompt?, alternate: ProximityPrompt?)
    local state = states[house]
    if not state or state.socket ~= socket then return end
    state.primaryPrompt = primary
    state.alternatePrompt = alternate
    syncPromptState(state)
end

function Service.Unregister(house: Model)
    local state = states[house]
    if not state then return end
    states[house] = nil
    if state.steam then state.steam:Destroy() end
    if state.fireAnchor then state.fireAnchor:Destroy() end
    if state.runtimeFolder then state.runtimeFolder:Destroy() end
    local socket = state.socket
    for _, name in {"Game1FireplaceFuelState", "Game1FireplaceFuelEndsAt", "Game1FireplaceFuelDuration", "Game1FireplacePotPresent", "Game1FireplaceCookState", "Game1FireplaceCookEndsAt", "Game1FireplaceCookDuration", "Game1FireplaceVisibleRadius"} do
        socket:SetAttribute(name, nil)
    end
end

function Service.Interact(house: Model, player: Player, key: string)
    local state = states[house]
    if not state then return end
    if key == "F" then
        if state.potInstance and state.potState == "idle" then
            removePot(state)
            notify(player, "Котел убран")
        end
        return
    end
    if state.fuelStage == "empty" and not state.potInstance then
        startFire(state)
        notify(player, {kind = "resource", items = {
            {icon = Config.ResourceSpend.Wood.icon, amount = -Config.ResourceSpend.Wood.amount, label = Config.ResourceSpend.Wood.label}
        }})
        notify(player, "Огонь разожжён")
        return
    end
    if state.fuelStage == "firewood" and not state.potInstance then
        placePot(state)
        notify(player, "Котел установлен")
        return
    end
    if state.potInstance then
        if state.potState == "idle" then
            if state.fuelStage == "empty" then
                notify(player, "Нужны дрова или угли")
                return
            end
            startCooking(state, player)
            notify(player, {kind = "resource", items = {
                {icon = Config.ResourceSpend.Carrot.icon, amount = -Config.ResourceSpend.Carrot.amount, label = Config.ResourceSpend.Carrot.label},
                {icon = Config.ResourceSpend.Onion.icon, amount = -Config.ResourceSpend.Onion.amount, label = Config.ResourceSpend.Onion.label},
                {icon = Config.ResourceSpend.Potato.icon, amount = -Config.ResourceSpend.Potato.amount, label = Config.ResourceSpend.Potato.label},
            }})
            notify(player, "Ингредиенты добавлены")
            return
        elseif state.potState == "ready" then
            state.potState = "idle"
            state.cookEndsAt = 0
            state.cookDuration = 0
            state.cookOwner = nil
            syncAttributes(state)
            notify(player, "Блюдо получено")
            return
        end
    end
end

return table.freeze(Service)
