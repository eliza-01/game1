-- Client-only anchored pendulum presentation. The rig and its authored pivot
-- remain intact; the model rotates around its stored mount point. No joints,
-- unanchored parts, continuous server physics or per-frame remotes.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local SoundService = game:GetService("SoundService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Config = require(Shared:WaitForChild("world"):WaitForChild("LandscapeSwayConfig"))
local Controller = {}
local active: {[Model]: any} = {}
local connection: RBXScriptConnection? = nil
local random = Random.new()
local DOWN = -Vector3.yAxis
local lastDraw = 0

local function horizontal(vector: Vector3): Vector3
    local flat = Vector3.new(vector.X, 0, vector.Z)
    return if flat.Magnitude > 0.001 then flat.Unit else Vector3.xAxis
end

-- Shortest rotation aligning a direction with gravity. For an inverted
-- lantern choose a stable horizontal axis rather than a zero cross product.
local function alignToGravity(vector: Vector3): CFrame
    if vector.Magnitude < 0.015 then return CFrame.identity end
    local direction = vector.Unit
    local cosine = math.clamp(direction:Dot(DOWN), -1, 1)
    if cosine >= 0.99999 then return CFrame.identity end
    local axis = direction:Cross(DOWN)
    if axis.Magnitude < 0.001 then axis = Vector3.xAxis end
    return CFrame.fromAxisAngle(axis.Unit, math.acos(cosine))
end

local function rotateAround(point: Vector3, rotation: CFrame): CFrame
    return CFrame.new(point) * rotation * CFrame.new(-point)
end

local function gravityPose(model: Model, anchor: Vector3, pivot: CFrame): CFrame
    -- First make the rope vertical. Then align the approximate visual centre
    -- of mass beneath the ORIGINAL rig pivot, without changing PivotOffset.
    local rope = rotateAround(anchor, alignToGravity(pivot.Position - anchor))
    local hanging = rope * pivot
    local visual = model:FindFirstChild("LandscapeSwayTarget")
    if visual and visual:IsA("BasePart") then
        local centre = rope:PointToWorldSpace(visual.Position)
        hanging = rotateAround(hanging.Position, alignToGravity(centre - hanging.Position)) * hanging
    end
    return hanging
end

local function positionLine(model: Model, anchor: Vector3, target: Vector3)
    local line = model:FindFirstChild("LandscapeAttachmentLine")
    if not line or not line:IsA("Part") or line:GetAttribute("Game1LandscapeAttachment") ~= true then return end
    local delta = target - anchor
    if delta.Magnitude <= 0.01 then return end
    local direction = delta.Unit
    local reference = if math.abs(direction:Dot(Vector3.yAxis)) > 0.94 then Vector3.xAxis else Vector3.yAxis
    local back = direction:Cross(reference).Unit
    line.Size = Vector3.new(delta.Magnitude, line.Size.Y, line.Size.Z)
    line.CFrame = CFrame.fromMatrix((anchor + target) * 0.5, direction, back:Cross(direction).Unit, back)
end

-- Game1 characters use RootCollider, not HumanoidRootPart. Reuse the same
-- physical root as MovementController and CameraController; retain Roblox
-- avatar compatibility for Play tests using the default character rig.
local function viewerPosition(): Vector3?
    local character = Players.LocalPlayer.Character
    if not character then return nil end
    local root = character:FindFirstChild("RootCollider")
        or character:FindFirstChild("HumanoidRootPart")
        or character:FindFirstChild("NavigationRoot")
    return if root and root:IsA("BasePart") then root.Position else nil
end

local function near(model: Model, position: Vector3?): boolean
    return position ~= nil and (position - model:GetPivot().Position).Magnitude <= Config.Radius
end

local function add(model: Model)
    if active[model] or model:GetAttribute("LandscapeSwayEnabled") ~= true
        or model:GetAttribute("LandscapeTetherEnabled") ~= true then return end
    local anchor = model:GetAttribute("LandscapeSurfacePoint")
    if typeof(anchor) ~= "Vector3" then return end
    local pivot = model:GetPivot()
    if (pivot.Position - anchor).Magnitude <= 0.025 then return end
    local rest = gravityPose(model, anchor, pivot)
    local azimuth = random:NextNumber(-math.pi, math.pi)
    active[model] = {
        anchor = anchor,
        original = pivot,
        rest = rest,
        entered = os.clock(),
        phase = random:NextNumber(0, math.pi * 2),
        ambientAxis = DOWN:Cross(Vector3.new(math.cos(azimuth), 0, math.sin(azimuth))).Unit,
        ambientAngle = Config.AmbientAngle * random:NextNumber(0.65, 1),
        impact = nil,
        wind = nil,
    }
end

local function tickSway()
    local now = os.clock()
    if now - lastDraw < 1 / Config.PresentationHz then return end
    lastDraw = now
    local position = viewerPosition()
    for model, state in pairs(active) do
        if not model.Parent or not near(model, position) or model:GetAttribute("LandscapeSwayEnabled") ~= true then
            if model.Parent then
                model:PivotTo(state.rest)
                positionLine(model, state.anchor, state.rest.Position)
            end
            active[model] = nil
        else
            local t = now - state.entered
            -- Ease from the edited pose into the gravity rest pose once on
            -- entering range; do not reset this when a hit or wind arrives.
            local settle = math.clamp(t / Config.SettleSeconds, 0, 1)
            settle = 1 - (1 - settle) ^ 3
            local base = state.original:Lerp(state.rest, settle)
            local ambient = state.ambientAngle * math.sin(now * Config.AmbientFrequency + state.phase)
            local angleFrame = CFrame.fromAxisAngle(state.ambientAxis, ambient)
            if state.impact then
                local elapsed = now - state.impact.at
                if elapsed > Config.Duration then
                    state.impact = nil
                else
                    local angle = state.impact.amplitude * math.exp(-Config.Decay * elapsed)
                        * math.sin(Config.Frequency * elapsed)
                    angleFrame = CFrame.fromAxisAngle(state.impact.axis, angle) * angleFrame
                end
            end
            if state.wind then
                local elapsed = now - state.wind.at
                if elapsed > state.wind.seconds then
                    state.wind = nil
                elseif elapsed >= 0 then
                    local fade = math.min(1, elapsed * 2, (state.wind.seconds - elapsed) * 1.3)
                    local angle = state.wind.amplitude * math.max(0, fade)
                        * math.sin(now * Config.WindFrequency + state.phase)
                    angleFrame = CFrame.fromAxisAngle(state.wind.axis, angle) * angleFrame
                end
            end
            local frame = rotateAround(state.anchor, angleFrame) * base
            model:PivotTo(frame)
            positionLine(model, state.anchor, frame.Position)
        end
    end
    if not next(active) and connection then connection:Disconnect(); connection = nil end
end

local function ensureRunning()
    if not connection and next(active) then
        connection = RunService.RenderStepped:Connect(tickSway)
    end
end

local function scanNearby()
    local folder = workspace:FindFirstChild("Game1LandscapeDecor")
    local position = viewerPosition()
    if not folder or not position then return end
    local candidates = {}
    for _, item in ipairs(folder:GetDescendants()) do
        if item:IsA("Model") and item:GetAttribute("LandscapeSwayEnabled") == true then
            local distance = (position - item:GetPivot().Position).Magnitude
            if distance <= Config.Radius then
                table.insert(candidates, {model = item, distance = distance})
            end
        end
    end
    table.sort(candidates, function(a, b) return a.distance < b.distance end)
    local wanted = {}
    for i = 1, math.min(Config.AmbientMaxTargets, #candidates) do
        local model = candidates[i].model
        wanted[model] = true
        add(model)
    end
    -- A hard active cap matters on mobile. Exit smoothly to the gravity rest
    -- position when a model drops out of the closest visible set.
    for model, state in pairs(active) do
        if not wanted[model] then
            if model.Parent then
                model:PivotTo(state.rest)
                positionLine(model, state.anchor, state.rest.Position)
            end
            active[model] = nil
        end
    end
    ensureRunning()
end

local function impact(model: Model, direction: Vector3)
    if not near(model, viewerPosition()) then return end
    add(model)
    local state = active[model]
    if not state then return end
    local axis = DOWN:Cross(horizontal(direction))
    state.impact = {
        axis = axis.Unit,
        amplitude = Config.ImpactAngle,
        at = os.clock(),
    }
    ensureRunning()
end

local function wind(strength: number, seconds: number)
    if strength <= 0 or seconds <= 0 then return end
    if Config.WindSoundId ~= "" then
        local sound = Instance.new("Sound")
        sound.SoundId = Config.WindSoundId
        sound.Volume = math.clamp(strength, 0, 1) * 0.7
        sound.Parent = SoundService
        sound.Ended:Once(function() sound:Destroy() end)
        sound:Play()
    end
    scanNearby()
    local count = 0
    for _, state in pairs(active) do
        count += 1
        if count > Config.WindMaxTargets then break end
        local direction = horizontal(Vector3.new(random:NextNumber(-1, 1), 0, random:NextNumber(-1, 1)))
        state.wind = {
            axis = DOWN:Cross(direction).Unit,
            amplitude = Config.WindAngle * strength * random:NextNumber(0.5, 1),
            at = os.clock() + random:NextNumber(0, math.min(1, seconds * 0.25)),
            seconds = seconds,
        }
    end
end

function Controller.Start()
    -- Periodic bounded discovery supports streaming and already placed assets;
    -- the 24 Hz visual loop is disconnected when no targets are nearby.
    task.spawn(function()
        while true do
            scanNearby()
            task.wait(Config.AmbientScanSeconds)
        end
    end)
    local remote = ReplicatedStorage:WaitForChild("Game1Remotes"):WaitForChild("LandscapeSwayEvent")
    remote.OnClientEvent:Connect(function(event, one, two)
        if event == "impact" and typeof(one) == "Instance" and one:IsA("Model")
            and typeof(two) == "Vector3" then
            impact(one, two)
        elseif event == "wind" and type(one) == "number" and type(two) == "number" then
            wind(math.clamp(one, 0, 1), math.clamp(two, 0, 30))
        end
    end)
end

return table.freeze(Controller)
