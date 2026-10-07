local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local CombatFeedbackController = {}
local started = false
local floatingSerial = 0
local MAX_DISTANCE = 160
local DAMAGE_LIFETIME = 0.95
local DAMAGE_RISE_STUDS = 1.65
local DAMAGE_ABOVE_TARGET_STUDS = 2.9

local function targetRoot(target: any): BasePart?
    if typeof(target) ~= "Instance" or not target:IsA("Model") or not target.Parent then return nil end
    local root = target:FindFirstChild("RootCollider") or target:FindFirstChild("HumanoidRootPart") or target.PrimaryPart
    return if root and root:IsA("BasePart") then root else nil
end

local function visibleTopOffset(model: Model, root: BasePart): number
    local topY = -math.huge
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") and descendant.Transparency < 1 and descendant.Name ~= "RootCollider" and descendant.Name ~= "HumanoidRootPart" then
            local half = descendant.Size * 0.5
            local frame = descendant.CFrame
            local extent = math.abs(frame.RightVector.Y) * half.X + math.abs(frame.UpVector.Y) * half.Y + math.abs(frame.LookVector.Y) * half.Z
            topY = math.max(topY, frame.Position.Y + extent)
        end
    end
    if topY == -math.huge then return 3.5 end
    return math.max(1, topY - root.Position.Y + 0.65)
end

local function makeWorldMarker(position: Vector3): BasePart
    local marker = Instance.new("Part")
    marker.Name = "Game1CombatFeedback"
    marker.Size = Vector3.new(0.05, 0.05, 0.05)
    marker.CFrame = CFrame.new(position)
    marker.Transparency = 1
    marker.Anchored = true
    marker.CanCollide = false
    marker.CanTouch = false
    marker.CanQuery = false
    marker.Parent = Workspace
    return marker
end

local function showDamage(target: any, fallbackPosition: Vector3, amount: number, incoming: boolean, critical: boolean)
    floatingSerial += 1
    local lane = (floatingSerial % 3) - 1
    local root = targetRoot(target)
    local parent: Instance
    local offset: Vector3
    if root and target:IsA("Model") then
        parent = root
        offset = Vector3.new(lane * 0.28, visibleTopOffset(target, root) + DAMAGE_ABOVE_TARGET_STUDS, 0)
    else
        parent = makeWorldMarker(fallbackPosition + Vector3.new(lane * 0.28, DAMAGE_ABOVE_TARGET_STUDS, 0))
        offset = Vector3.zero
    end

    local gui = Instance.new("BillboardGui")
    gui.Name = incoming and "IncomingDamageNumber" or "CombatDamageNumber"
    gui.Adornee = root or (parent:IsA("BasePart") and parent or nil)
    gui.AlwaysOnTop = true
    gui.LightInfluence = 0
    gui.MaxDistance = MAX_DISTANCE
    gui.Size = UDim2.fromOffset(100, 30)
    gui.StudsOffsetWorldSpace = offset
    gui.Parent = parent

    local label = Instance.new("TextLabel")
    label.BackgroundTransparency = 1
    label.Size = UDim2.fromScale(1, 1)
    label.Font = Enum.Font.GothamBold
    label.Text = tostring(math.max(1, math.floor(amount + 0.5)))
    label.TextColor3 = if incoming then Color3.fromRGB(255, 82, 82) else (critical and Color3.fromRGB(255, 196, 82) or Color3.fromRGB(255, 225, 145))
    label.TextSize = critical and 17 or 15
    label.TextStrokeColor3 = if incoming then Color3.fromRGB(72, 8, 8) else Color3.fromRGB(49, 15, 8)
    label.TextStrokeTransparency = 0.12
    label.Parent = gui

    local scale = Instance.new("UIScale")
    scale.Scale = 0.72
    scale.Parent = label
    TweenService:Create(scale, TweenInfo.new(0.14, Enum.EasingStyle.Back, Enum.EasingDirection.Out), {Scale = 1}):Play()
    TweenService:Create(gui, TweenInfo.new(0.9, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {StudsOffsetWorldSpace = offset + Vector3.new(0, DAMAGE_RISE_STUDS, 0)}):Play()
    TweenService:Create(label, TweenInfo.new(0.62, Enum.EasingStyle.Quad, Enum.EasingDirection.In, 0, false, 0.24), {TextTransparency = 1, TextStrokeTransparency = 1}):Play()
    task.delay(DAMAGE_LIFETIME, function()
        if gui.Parent then gui:Destroy() end
        if not root and parent.Parent then parent:Destroy() end
    end)
end

function CombatFeedbackController.Start()
    if started then return end
    started = true
    local remote = ReplicatedStorage:WaitForChild("Game1Remotes"):WaitForChild("CombatFeedback")
    if not remote:IsA("RemoteEvent") then return end
    remote.OnClientEvent:Connect(function(payload: any)
        if type(payload) ~= "table" or tostring(payload.kind or "") ~= "damage" then return end
        local position = payload.position
        local damage = tonumber(payload.damage) or 0
        if typeof(position) ~= "Vector3" or damage <= 0 then return end
        showDamage(payload.target, position, damage, tostring(payload.relation or "") == "incoming", payload.critical == true)
    end)
end

return table.freeze(CombatFeedbackController)
