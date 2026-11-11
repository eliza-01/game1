-- Touch-only input adapter for Game1's custom ControllerManager and Scriptable camera.
-- The stock Roblox PlayerModule is intentionally disabled in default.project.json.
-- No physics, camera ownership or combat validation lives in this module.
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local MobileInputController = {}
local started = false

local PALETTE = {
    background = Color3.fromRGB(0, 0, 0),
    rim = Color3.fromRGB(240, 240, 240),
    thumb = Color3.fromRGB(255, 255, 255),
    accent = Color3.fromRGB(255, 255, 255),
    text = Color3.fromRGB(244, 251, 249),
}

local DEADZONE = 0.12

local function circle(parent: Instance, size: number, background: Color3, transparency: number): Frame
    local frame = Instance.new("Frame")
    frame.BackgroundColor3 = background
    frame.BackgroundTransparency = transparency
    frame.BorderSizePixel = 0
    frame.Size = UDim2.fromOffset(size, size)
    frame.Parent = parent
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(1, 0)
    corner.Parent = frame
    return frame
end

local function stroke(frame: GuiObject, color: Color3, transparency: number, thickness: number)
    local outline = Instance.new("UIStroke")
    outline.Color = color
    outline.Transparency = transparency
    outline.Thickness = thickness
    outline.Parent = frame
end

local function makeStick(gui: ScreenGui, name: string)
    local pad = circle(gui, 120, PALETTE.background, 0.57)
    pad.Name = name
    pad.Active = true
    pad.AnchorPoint = Vector2.new(0, 1)
    stroke(pad, PALETTE.rim, 0.72, 1.5)

    local inner = circle(pad, 56, PALETTE.thumb, 0.42)
    inner.Name = "Thumb"
    inner.AnchorPoint = Vector2.new(0.5, 0.5)
    inner.Position = UDim2.fromScale(0.5, 0.5)
    inner.Visible = false -- only show the white thumb while a finger owns this pad
    inner.Active = false

    return { pad = pad, thumb = inner, input = nil :: InputObject?, axis = Vector2.zero }
end

-- Icons are vector-like Roblox UI primitives, not asset IDs or text glyphs.
-- Their images therefore work on a fresh device without uploading textures.
local function iconLine(parent: Instance, name: string, width: number, height: number,
    x: number, y: number, rotation: number)
    local line = Instance.new("Frame")
    line.Name = name
    line.AnchorPoint = Vector2.new(0.5, 0.5)
    line.Position = UDim2.fromScale(x, y)
    line.Size = UDim2.fromScale(width, height)
    line.Rotation = rotation
    line.BackgroundColor3 = PALETTE.text
    line.BackgroundTransparency = 0.06
    line.BorderSizePixel = 0
    line.Parent = parent
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 2)
    corner.Parent = line
end

local function makeAction(gui: ScreenGui, name: string): TextButton
    local button = Instance.new("TextButton")
    button.Name = name
    button.AnchorPoint = Vector2.new(1, 1)
    button.BackgroundColor3 = Color3.new(0, 0, 0)
    button.BackgroundTransparency = 0.48
    button.BorderSizePixel = 0
    button.AutoButtonColor = true
    button.Text = ""
    button.ZIndex = 3
    button.Parent = gui
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(1, 0)
    corner.Parent = button
    stroke(button, PALETTE.rim, 0.72, 1)
    local glyph = Instance.new("Frame")
    glyph.Name = name .. "Icon"
    glyph.AnchorPoint = Vector2.new(0.5, 0.5)
    glyph.Position = UDim2.fromScale(0.5, 0.5)
    glyph.Size = UDim2.fromScale(0.6, 0.6)
    glyph.BackgroundTransparency = 1
    glyph.Parent = button
    if name == "Attack" then
        -- Tilted sword silhouette: pointed blade, cross guard and grip.
        iconLine(glyph, "Blade", 0.16, 0.66, 0.53, 0.34, 45)
        iconLine(glyph, "Crossguard", 0.43, 0.09, 0.37, 0.58, 45)
        iconLine(glyph, "Grip", 0.10, 0.27, 0.22, 0.79, 45)
        iconLine(glyph, "Pommel", 0.19, 0.10, 0.13, 0.89, 45)
    else
        -- Jumping figure, arms extended and one bent leg.
        local head = circle(glyph, 7, PALETTE.text, 0.04)
        head.Name = "Head"
        head.AnchorPoint = Vector2.new(0.5, 0.5)
        head.Position = UDim2.fromScale(0.51, 0.18)
        head.Size = UDim2.fromScale(0.2, 0.2)
        iconLine(glyph, "Body", 0.10, 0.35, 0.5, 0.48, 0)
        iconLine(glyph, "LeftArm", 0.35, 0.09, 0.32, 0.36, 30)
        iconLine(glyph, "RightArm", 0.35, 0.09, 0.68, 0.36, -30)
        iconLine(glyph, "LeftLeg", 0.11, 0.34, 0.38, 0.75, 43)
        iconLine(glyph, "RightLeg", 0.11, 0.34, 0.65, 0.75, -43)
    end
    return button
end

local function getTouchPosition(input: InputObject): Vector2
    return Vector2.new(input.Position.X, input.Position.Y)
end

local function stickCenter(stick): Vector2
    return stick.pad.AbsolutePosition + stick.pad.AbsoluteSize * 0.5
end

local function touchStartsOn(stick, input: InputObject): boolean
    local center = stickCenter(stick)
    local radius = stick.pad.AbsoluteSize.X * 0.5
    return (getTouchPosition(input) - center).Magnitude <= radius
end

local function moveStick(stick, input: InputObject)
    local center = stickCenter(stick)
    local radius = math.max(1, stick.pad.AbsoluteSize.X * 0.35)
    local delta = getTouchPosition(input) - center
    local magnitude = delta.Magnitude
    local limited = if magnitude > radius then delta.Unit * radius else delta
    stick.thumb.Visible = true
    stick.thumb.Position = UDim2.new(0.5, limited.X, 0.5, limited.Y)

    local normalized = limited / radius
    local strength = math.clamp((normalized.Magnitude - DEADZONE) / (1 - DEADZONE), 0, 1)
    -- Screen Y increases downward; game forward/camera up increase with positive Y.
    stick.axis = if strength > 0 then Vector2.new(normalized.X, -normalized.Y).Unit * strength else Vector2.zero
end

local function releaseStick(stick)
    stick.input = nil
    stick.axis = Vector2.zero
    stick.thumb.Position = UDim2.fromScale(0.5, 0.5)
    stick.thumb.Visible = false
end

function MobileInputController.Start(movementController: any, cameraController: any, attackController: any)
    if started or not UserInputService.TouchEnabled then
        return
    end
    started = true

    local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")
    local existing = playerGui:FindFirstChild("Game1MobileControls")
    if existing then
        existing:Destroy()
    end
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1MobileControls"
    gui.ResetOnSpawn = false
    gui.DisplayOrder = 15
    gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
    gui.Parent = playerGui

    local left = makeStick(gui, "MoveStick")
    local right = makeStick(gui, "LookStick")
    right.pad.AnchorPoint = Vector2.new(1, 1)

    local jump = makeAction(gui, "Jump")
    local attack = makeAction(gui, "Attack")

    local function layout()
        local camera = Workspace.CurrentCamera
        if not camera then
            return
        end
        local viewport = camera.ViewportSize
        local short = math.min(viewport.X, viewport.Y)
        local stickSize = math.floor(math.clamp(short * 0.31, 105, 148))
        local inset = math.floor(math.clamp(short * 0.07, 19, 34))
        local sideInset = math.floor(math.clamp(viewport.X * 0.035, 20, 44))
        local actionSize = math.floor(math.clamp(stickSize * 0.5, 49, 70))
        local thumbSize = math.floor(stickSize * 0.47)
        left.pad.Size = UDim2.fromOffset(stickSize, stickSize)
        right.pad.Size = UDim2.fromOffset(stickSize, stickSize)
        left.pad.Position = UDim2.new(0, sideInset, 1, -inset)
        right.pad.Position = UDim2.new(1, -sideInset, 1, -inset)
        left.thumb.Size = UDim2.fromOffset(thumbSize, thumbSize)
        right.thumb.Size = UDim2.fromOffset(thumbSize, thumbSize)
        jump.Size = UDim2.fromOffset(actionSize, actionSize)
        attack.Size = UDim2.fromOffset(actionSize, actionSize)
        jump.Position = UDim2.new(1, -sideInset, 1, -inset - stickSize - 22)
        attack.Position = UDim2.new(1, -sideInset - actionSize - 14, 1, -inset - stickSize - 22)
    end

    local cameraConnection: RBXScriptConnection? = nil
    local function bindViewport()
        if cameraConnection then
            cameraConnection:Disconnect()
            cameraConnection = nil
        end
        local camera = Workspace.CurrentCamera
        if camera then
            cameraConnection = camera:GetPropertyChangedSignal("ViewportSize"):Connect(layout)
        end
        layout()
    end
    Workspace:GetPropertyChangedSignal("CurrentCamera"):Connect(bindViewport)
    bindViewport()

    local function resetTouch()
        releaseStick(left)
        releaseStick(right)
        movementController.SetTouchMovement(Vector2.zero, false)
        cameraController.SetTouchLookAxis(Vector2.zero)
    end

    -- Track each InputObject separately. One finger cannot steal the other stick.
    UserInputService.TouchStarted:Connect(function(input: InputObject)
        if UserInputService:GetFocusedTextBox() ~= nil then
            return
        end
        if not left.input and touchStartsOn(left, input) then
            left.input = input
            moveStick(left, input)
            movementController.SetTouchMovement(left.axis, true)
        elseif not right.input and touchStartsOn(right, input) then
            right.input = input
            moveStick(right, input)
            cameraController.SetTouchLookAxis(right.axis)
        end
    end)

    UserInputService.TouchMoved:Connect(function(input: InputObject)
        if input == left.input then
            moveStick(left, input)
            movementController.SetTouchMovement(left.axis, true)
        elseif input == right.input then
            moveStick(right, input)
            cameraController.SetTouchLookAxis(right.axis)
        end
    end)

    UserInputService.TouchEnded:Connect(function(input: InputObject)
        if input == left.input then
            releaseStick(left)
            movementController.SetTouchMovement(Vector2.zero, false)
        elseif input == right.input then
            releaseStick(right)
            cameraController.SetTouchLookAxis(Vector2.zero)
        end
    end)

    UserInputService.WindowFocusReleased:Connect(resetTouch)
    jump.Activated:Connect(function()
        movementController.RequestJump()
    end)
    attack.Activated:Connect(function()
        if attackController.RequestAttack then
            attackController.RequestAttack()
        end
    end)
end

return MobileInputController
