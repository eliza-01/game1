local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local CombatFloatingText = {}

local MAX_DISTANCE = 160
local DAMAGE_LIFETIME = 0.95
local DAMAGE_RISE_STUDS = 1.65
local DAMAGE_ABOVE_TARGET_STUDS = 2.9
local CRITICAL_LIFETIME = 0.82
local CRITICAL_RISE_STUDS = 0.9
local CRITICAL_ABOVE_TARGET_STUDS = 2.15
local floatingSerial = 0

local function targetRoot(target: any): BasePart?
    if typeof(target) ~= "Instance" or not target:IsA("Model") or not target.Parent then
        return nil
    end
    local root = target:FindFirstChild("RootCollider") or target:FindFirstChild("HumanoidRootPart") or target.PrimaryPart
    return if root and root:IsA("BasePart") then root else nil
end

local function visibleTopOffset(model: Model, root: BasePart): number
    local topY = -math.huge
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart")
            and descendant.Transparency < 1
            and descendant.Name ~= "RootCollider"
            and descendant.Name ~= "HumanoidRootPart"
        then
            local half = descendant.Size * 0.5
            local frame = descendant.CFrame
            local extent = math.abs(frame.RightVector.Y) * half.X
                + math.abs(frame.UpVector.Y) * half.Y
                + math.abs(frame.LookVector.Y) * half.Z
            topY = math.max(topY, frame.Position.Y + extent)
        end
    end
    if topY == -math.huge then
        return 3.5
    end
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
    marker.CastShadow = false
    marker.Parent = Workspace
    return marker
end

local function targetAnchor(target: any, fallbackPosition: Vector3, aboveStuds: number, laneX: number?): (Instance, BasePart?, Vector3)
    local root = targetRoot(target)
    if root and target:IsA("Model") then
        return root, root, Vector3.new(laneX or 0, visibleTopOffset(target, root) + aboveStuds, 0)
    end
    local marker = makeWorldMarker(fallbackPosition + Vector3.new(laneX or 0, aboveStuds, 0))
    return marker, marker, Vector3.zero
end

local function cleanupBillboard(gui: BillboardGui, parent: Instance, root: BasePart?, delaySeconds: number)
    task.delay(delaySeconds, function()
        if gui.Parent then
            gui:Destroy()
        end
        if not root and parent.Parent then
            parent:Destroy()
        end
    end)
end

function CombatFloatingText.ShowDamage(target: any, fallbackPosition: Vector3, amount: number, incoming: boolean, critical: boolean)
    floatingSerial += 1
    local lane = (floatingSerial % 3) - 1
    local parent, root, offset = targetAnchor(target, fallbackPosition, DAMAGE_ABOVE_TARGET_STUDS, lane * 0.28)

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
    label.TextColor3 = if incoming
        then Color3.fromRGB(255, 82, 82)
        else (critical and Color3.fromRGB(255, 196, 82) or Color3.fromRGB(255, 225, 145))
    label.TextSize = critical and 17 or 15
    label.TextStrokeColor3 = if incoming then Color3.fromRGB(72, 8, 8) else Color3.fromRGB(49, 15, 8)
    label.TextStrokeTransparency = 0.12
    label.Parent = gui

    local scale = Instance.new("UIScale")
    scale.Scale = 0.72
    scale.Parent = label
    TweenService:Create(scale, TweenInfo.new(0.14, Enum.EasingStyle.Back, Enum.EasingDirection.Out), { Scale = 1 }):Play()
    TweenService:Create(gui, TweenInfo.new(0.9, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
        StudsOffsetWorldSpace = offset + Vector3.new(0, DAMAGE_RISE_STUDS, 0),
    }):Play()
    TweenService:Create(label, TweenInfo.new(0.62, Enum.EasingStyle.Quad, Enum.EasingDirection.In, 0, false, 0.24), {
        TextTransparency = 1,
        TextStrokeTransparency = 1,
    }):Play()
    cleanupBillboard(gui, parent, root, DAMAGE_LIFETIME)
end

function CombatFloatingText.ShowCritical(target: any, fallbackPosition: Vector3)
    local parent, root, offset = targetAnchor(target, fallbackPosition, CRITICAL_ABOVE_TARGET_STUDS)

    local gui = Instance.new("BillboardGui")
    gui.Name = "CriticalBillboard"
    gui.Adornee = root or (parent:IsA("BasePart") and parent or nil)
    gui.Size = UDim2.fromOffset(128, 30)
    gui.StudsOffsetWorldSpace = offset
    gui.AlwaysOnTop = true
    gui.LightInfluence = 0
    gui.MaxDistance = MAX_DISTANCE
    gui.Parent = parent

    local label = Instance.new("TextLabel")
    label.Name = "Label"
    label.BackgroundTransparency = 1
    label.Size = UDim2.fromScale(1, 1)
    label.Font = Enum.Font.GothamBold
    label.Text = "Critical!"
    label.TextColor3 = Color3.fromRGB(255, 213, 112)
    label.TextSize = 15
    label.TextStrokeColor3 = Color3.fromRGB(20, 17, 13)
    label.TextStrokeTransparency = 0.22
    label.Parent = gui

    local scale = Instance.new("UIScale")
    scale.Scale = 0.78
    scale.Parent = gui
    TweenService:Create(scale, TweenInfo.new(0.13, Enum.EasingStyle.Back, Enum.EasingDirection.Out), { Scale = 1 }):Play()

    task.delay(0.16, function()
        if not gui.Parent then
            return
        end
        TweenService:Create(gui, TweenInfo.new(CRITICAL_LIFETIME - 0.16, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
            StudsOffsetWorldSpace = offset + Vector3.new(0, CRITICAL_RISE_STUDS, 0),
        }):Play()
        TweenService:Create(label, TweenInfo.new(CRITICAL_LIFETIME - 0.16, Enum.EasingStyle.Quad, Enum.EasingDirection.In), {
            TextTransparency = 1,
            TextStrokeTransparency = 1,
        }):Play()
    end)

    cleanupBillboard(gui, parent, root, CRITICAL_LIFETIME + 0.05)
end

return table.freeze(CombatFloatingText)
