--!strict
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local WorldShared = Shared:WaitForChild("world")
local Mount = require(script.Parent:WaitForChild("HouseSocketAssetMount"))
local Config = require(WorldShared:WaitForChild("FireplaceMechanicsConfig"))

local Service = {}

type State = {
    house: Model,
    kind: string,
    socket: Attachment,
    potMountSocket: Attachment,
    chimney: ParticleEmitter?,
    fireAuthored: boolean,
    lightAuthored: boolean,
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
    steamAnchor: Attachment?,
    potState: string,
    cookEndsAt: number,
    cookDuration: number,
    cookRevision: number,
    cookOwner: Player?,
}

local states: {[Model]: State} = {}
local feedbackRemote: RemoteEvent? = nil

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
    local socket = state.socket
    local anchor = Instance.new("Attachment")
    -- Reuse the Fire Tuner / BoneFireController world-up contract. The Fire
    -- starts exactly at the Bone HEAD (Attachment local zero) and emits +Y.
    anchor.Name = if socket:IsA("Bone") then "Game1FireDirectionFireplace"
        else "Game1FireplaceFireAnchor"
    local socketFrame = getFrame(socket)
    anchor.CFrame = socketFrame.Rotation:Inverse()
    anchor:SetAttribute("Game1FireWorldUp", true)
    anchor.Parent = socket
    state.fireAnchor = anchor
    return anchor
end

local function ensureFireVisual(state: State, enabled: boolean)
    local fire = state.fire
    -- Reuse authored Fire/PointLight from Fire Tuner when present; never
    -- duplicate them. Gameplay mode owns the actual visual preset now.
    if state.kind == "campfire" and not fire then
        for _, child in ipairs(state.socket:GetDescendants()) do
            if child:IsA("Fire") and not state.fire then
                state.fire = child
                state.fireAuthored = true
            elseif child:IsA("PointLight") and not state.light then
                state.light = child
                state.lightAuthored = true
            end
        end
        fire = state.fire
    end
    -- Campfire changes BOTH Fire and PointLight on the same live Instances:
    -- no pot = reference profile; pot = house fireplace profile.
    -- Mode changes never restart the heat timer or recreate the effects.
    local referenceMode = state.kind == "campfire" and state.potInstance == nil
    local firePreset = if referenceMode then Config.CampfireFire else Config.Fire
    local lightPreset = if referenceMode then Config.CampfireLight else Config.Light
    local anchor = if not fire or not state.light then fireAnchor(state) else nil
    if not fire then
        fire = Instance.new("Fire")
        fire.Name = if state.kind == "campfire" then "Game1CampfireFlame" else "Game1FireplaceFlame"
        fire.Parent = anchor
        state.fire = fire
    end
    -- Apply the exact Fire Tuner profile for each source, even when a
    -- pre-existing instance was discovered. That prevents the fallback path
    -- from silently reusing the House fireplace's smaller, cooler flame.
    fire.Size = firePreset.Size
    fire.Heat = firePreset.Heat
    fire.TimeScale = firePreset.TimeScale
    fire.Color = firePreset.Primary
    fire.SecondaryColor = firePreset.Secondary
    fire.Enabled = enabled
    local light = state.light
    if not light then
        light = Instance.new("PointLight")
        light.Name = if state.kind == "campfire" then "Game1CampfireLight" else "Game1FireplaceLight"
        light.Parent = anchor
        state.light = light
    end
    light.Brightness = lightPreset.Brightness
    light.Range = lightPreset.Range
    light.Color = lightPreset.Color
    light.Shadows = lightPreset.Shadows
    light.Enabled = enabled and lightPreset.Enabled
end

local function ensureSteam(state: State, enabled: boolean)
    local socket = state.potSocket
    if not socket or not socket.Parent then return end
    local anchor = state.steamAnchor
    if not anchor or not anchor.Parent then
        anchor = Instance.new("Attachment")
        anchor.Name = "Game1CookingSteamWorldUp"
        anchor.Parent = socket
        state.steamAnchor = anchor
    end
    -- ParticleEmitter.EmissionDirection uses its parent's local axes.
    -- Cancel the actual cooking_pot_socket world rotation, not only the
    -- acceleration, or steam from a tilted pot will shoot sideways.
    anchor.CFrame = getFrame(socket).Rotation:Inverse()
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
        steam.EmissionDirection = Enum.NormalId.Top
        steam.Parent = anchor
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
            if not state.potInstance or state.potState == "idle" then
                primary.ActionText = "Разжечь огонь"
                primary.Enabled = true
            elseif state.potState == "ready" then
                primary.ActionText = "Забрать блюдо"
                primary.Enabled = true
            else
                primary.ActionText = if state.potState == "cooking" then "Блюдо готовится" else "Камин"
                primary.Enabled = false
            end
        elseif (state.fuelStage == "firewood" or state.fuelStage == "fire") and not state.potInstance then
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
    if state.chimney then state.chimney.Enabled = state.fuelStage ~= "empty" end
end

local function replaceFuel(state: State, slug: string?): boolean
    local replacement: Model? = nil
    if slug and slug ~= "" then
        replacement = Mount.Spawn(slug, state.runtimeFolder, state.socket)
        if not replacement then return false end
    end
    if state.fuelInstance then state.fuelInstance:Destroy() end
    state.fuelInstance = replacement
    return true
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
    if state.kind == "campfire" then
        transitionToEmpty(state, revision)
        return
    end
    if not replaceFuel(state, "embers_01") then
        transitionToEmpty(state, revision)
        return
    end
    state.fuelStage = "embers"
    state.fuelDuration = Config.EmbersDurationSeconds
    state.fuelEndsAt = now() + Config.EmbersDurationSeconds
    ensureFireVisual(state, false)
    syncAttributes(state)
    task.delay(Config.EmbersDurationSeconds, function()
        transitionToEmpty(state, revision)
    end)
end

local function startFire(state: State): boolean
    if state.kind == "house" and not replaceFuel(state, "firewood_01") then return false end
    state.fuelRevision += 1
    state.fuelStage = if state.kind == "campfire" then "fire" else "firewood"
    state.fuelDuration = if state.kind == "campfire" then Config.CampfireDurationSeconds else Config.FuelDurationSeconds
    state.fuelEndsAt = now() + state.fuelDuration
    ensureFireVisual(state, true)
    syncAttributes(state)
    local revision = state.fuelRevision
    task.delay(state.fuelDuration, function()
        transitionToEmbers(state, revision)
    end)
    return true
end

local function removePot(state: State)
    if state.potInstance then state.potInstance:Destroy() end
    state.potInstance = nil
    state.potSocket = nil
    if state.steam then state.steam:Destroy(); state.steam = nil end
    if state.steamAnchor then state.steamAnchor:Destroy(); state.steamAnchor = nil end
    state.potState = "idle"
    state.cookEndsAt = 0
    state.cookDuration = 0
    state.cookOwner = nil
    if state.kind == "campfire" then ensureFireVisual(state, state.fuelStage == "fire") end
    syncAttributes(state)
end

local function placePot(state: State): boolean
    local ownerHeading = if state.kind == "campfire" then state.house:GetPivot().LookVector else nil
    local instance, potSocket = Mount.Spawn("cooking_pot_01", state.runtimeFolder, state.potMountSocket, ownerHeading)
    if not instance or not potSocket then return false end
    state.potInstance = instance
    state.potSocket = potSocket
    state.potState = "idle"
    state.cookEndsAt = 0
    state.cookDuration = 0
    if state.kind == "campfire" then ensureFireVisual(state, state.fuelStage == "fire") end
    syncAttributes(state)
    return true
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

local function register(house: Model, socket: Attachment, potSocket: Attachment, kind: string, generated: {Instance}?)
    if states[house] then return end
    local folder = Instance.new("Folder")
    folder.Name = "Game1FireplaceRuntime"
    folder.Parent = house
    local state: State = {
        house = house,
        kind = kind,
        socket = socket,
        potMountSocket = potSocket,
        chimney = nil,
        fireAuthored = false,
        lightAuthored = false,
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
        steamAnchor = nil,
        potState = "idle",
        cookEndsAt = 0,
        cookDuration = 0,
        cookRevision = 0,
        cookOwner = nil,
    }
    states[house] = state
    if generated then table.insert(generated, folder) end
    if kind == "campfire" then ensureFireVisual(state, false) end
    syncAttributes(state)
end

function Service.Register(house: Model, socket: Attachment, generated: {Instance}?)
    register(house, socket, socket, "house", generated)
end

function Service.RegisterCampfire(model: Model, fireSocket: Attachment, cookingSocket: Attachment)
    register(model, fireSocket, cookingSocket, "campfire", nil)
end

function Service.BindChimney(house: Model, emitter: ParticleEmitter)
    local state = states[house]
    if not state then
        emitter.Enabled = false
        return
    end
    state.chimney = emitter
    emitter.Enabled = state.fuelStage ~= "empty"
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
    if state.steamAnchor then state.steamAnchor:Destroy() end
    if state.fireAuthored and state.fire then state.fire.Enabled = false end
    if state.lightAuthored and state.light then state.light.Enabled = false end
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
    if state.fuelStage == "empty" and (not state.potInstance or state.potState == "idle") then
        if not startFire(state) then
            notify(player, "Дрова недоступны: проверь опубликованный firewood_01")
            return
        end
        notify(player, {kind = "resource", items = {
            {icon = Config.ResourceSpend.Wood.icon, amount = -Config.ResourceSpend.Wood.amount, label = Config.ResourceSpend.Wood.label}
        }})
        notify(player, "Огонь разожжён")
        return
    end
    if (state.fuelStage == "firewood" or state.fuelStage == "fire") and not state.potInstance then
        if placePot(state) then
            notify(player, "Котел установлен")
        else
            notify(player, "Котел недоступен: проверь модель и cooking_pot_socket")
        end
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
