-- Touch-only movement stick + free-screen camera drag/pinch adapter.
-- The stock Roblox PlayerModule is intentionally disabled in default.project.json.
-- No physics, camera ownership or combat validation lives in this module.
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))

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
    local pad = circle(gui, 68, PALETTE.background, 0.34)
    pad.Name = name
    -- Dynamic thumb zone: no permanent left joystick or touch-capturing GUI.
    pad.Active = false
    pad.Visible = false
    pad.AnchorPoint = Vector2.new(0.5, 0.5)
    pad:SetAttribute("WorldInputPassthrough", true)
    stroke(pad, PALETTE.rim, 0.80, 1)

    local inner = circle(pad, 28, PALETTE.thumb, 0.42)
    inner.Name = "Thumb"
    inner.AnchorPoint = Vector2.new(0.5, 0.5)
    inner.Position = UDim2.fromScale(0.5, 0.5)
    inner.Visible = false -- only show the white thumb while a finger owns this pad
    inner.Active = false

    return { pad = pad, thumb = inner, input = nil :: InputObject?, center = nil :: Vector2?, axis = Vector2.zero }
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
    if name == "Aim" then
        -- Reticle glyph, distinct from attack and jump.
        local ring = Instance.new("Frame")
        ring.Name = "ReticleRing"
        ring.AnchorPoint = Vector2.new(0.5, 0.5)
        ring.Position = UDim2.fromScale(0.5, 0.5)
        ring.Size = UDim2.fromScale(0.65, 0.65)
        ring.BackgroundTransparency = 1
        ring.Parent = glyph
        local round = Instance.new("UICorner")
        round.CornerRadius = UDim.new(1, 0)
        round.Parent = ring
        stroke(ring, PALETTE.text, 0.06, 2)
        iconLine(glyph, "ReticleTop", 0.07, 0.21, 0.5, 0.04, 0)
        iconLine(glyph, "ReticleBottom", 0.07, 0.21, 0.5, 0.96, 0)
        iconLine(glyph, "ReticleLeft", 0.21, 0.07, 0.04, 0.5, 0)
        iconLine(glyph, "ReticleRight", 0.21, 0.07, 0.96, 0.5, 0)
    elseif name == "Attack" then
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
    return stick.center or (stick.pad.AbsolutePosition + stick.pad.AbsoluteSize * 0.5)
end

local function moveStick(stick, input: InputObject)
    local center = stickCenter(stick)
    -- Movement radius is larger than the small visual circle: analog precision
    -- is preserved without putting a large control on screen.
    local radius = math.max(38, stick.pad.AbsoluteSize.X * 0.72)
    local delta = getTouchPosition(input) - center
    local magnitude = delta.Magnitude
    local limited = if magnitude > radius then delta.Unit * radius else delta
    local thumbLimit = stick.pad.AbsoluteSize.X * 0.28
    local visualDelta = if limited.Magnitude > thumbLimit
        then limited.Unit * thumbLimit else limited
    stick.thumb.Visible = true
    stick.thumb.Position = UDim2.new(0.5, visualDelta.X, 0.5, visualDelta.Y)

    local normalized = limited / radius
    local strength = math.clamp((normalized.Magnitude - DEADZONE) / (1 - DEADZONE), 0, 1)
    -- Screen Y increases downward; game forward/camera up increase with positive Y.
    stick.axis = if strength > 0 then Vector2.new(normalized.X, -normalized.Y).Unit * strength else Vector2.zero
end

local function releaseStick(stick)
    stick.input = nil
    stick.center = nil
    stick.pad.Visible = false
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
    -- Raw InputObject.Position and UDim2.fromOffset share one viewport origin.
    gui.IgnoreGuiInset = true
    gui.DisplayOrder = 15
    gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
    gui.Parent = playerGui

    local left = makeStick(gui, "MoveStick")

    local jump = makeAction(gui, "Jump")
    local attack = makeAction(gui, "Attack")
    local aim = makeAction(gui, "Aim")

    local function layout()
        local camera = Workspace.CurrentCamera
        if not camera then
            return
        end
        local viewport = camera.ViewportSize
        local short = math.min(viewport.X, viewport.Y)
        local oldStickSize = math.floor(math.clamp(short * 0.31, 105, 148))
        local stickSize = math.floor(math.clamp(short * 0.17, 58, 74))
        local inset = math.floor(math.clamp(short * 0.07, 19, 34))
        local sideInset = math.floor(math.clamp(viewport.X * 0.035, 20, 44))
        local actionSize = math.floor(math.clamp(oldStickSize * 0.5, 49, 70))
        left.pad.Size = UDim2.fromOffset(stickSize, stickSize)
        left.thumb.Size = UDim2.fromOffset(math.floor(stickSize * 0.40), math.floor(stickSize * 0.40))
        jump.Size = UDim2.fromOffset(actionSize, actionSize)
        attack.Size = UDim2.fromOffset(actionSize, actionSize)
        aim.Size = UDim2.fromOffset(actionSize, actionSize)
        -- Reserve the full former right joystick footprint as EMPTY, active
        -- camera-look space. Place action buttons outside that invisible circle.
        local virtualRadius = oldStickSize * 0.55
        local buttonDistance = virtualRadius + actionSize * 0.5 + 12
        local centerX = viewport.X - sideInset - (virtualRadius + actionSize + 18)
        local centerY = viewport.Y - inset - (virtualRadius + actionSize * 0.45)
        local function put(button: TextButton, x: number, y: number)
            button.Position = UDim2.fromOffset(math.floor(x + actionSize * 0.5),
                math.floor(y + actionSize * 0.5))
        end
        put(attack, centerX - buttonDistance, centerY - 18)
        put(aim, centerX + buttonDistance, centerY - 18)
        put(jump, centerX, centerY - buttonDistance)
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

    -- Up to two fingers on the world viewport control the camera. The movement
    -- finger and touch UI are never counted as look/pinch fingers.
    local lookFingers: {InputObject} = {}
    local lookPositions: {[InputObject]: Vector2} = {}
    local pinchGap: number? = nil
    local pinchLocked = false -- never interpret a surviving pinch finger as fresh one-finger input

    local function moveTouchZone(position: Vector2): boolean
        local camera = Workspace.CurrentCamera
        if not camera then return false end
        local size = camera.ViewportSize
        return position.X <= size.X / 3 and position.Y >= size.Y * 0.5
    end

    local function cameraTouchZone(position: Vector2): boolean
        local camera = Workspace.CurrentCamera
        return camera ~= nil and position.X >= camera.ViewportSize.X / 3
    end

    local function gapBetweenLookFingers(): number?
        if #lookFingers ~= 2 then
            return nil
        end
        return (lookPositions[lookFingers[1]] - lookPositions[lookFingers[2]]).Magnitude
    end

    local function resetTouch()
        releaseStick(left)
        movementController.SetTouchMovement(Vector2.zero, false)
        table.clear(lookFingers)
        table.clear(lookPositions)
        pinchGap = nil
        pinchLocked = false
    end

    UserInputService.TouchStarted:Connect(function(input: InputObject, gameProcessed: boolean)
        if UserInputService:GetFocusedTextBox() ~= nil then
            return
        end
        if not left.input and moveTouchZone(getTouchPosition(input))
            and not UiInputGuard.BlocksWorldInput(input, gameProcessed) then
            left.center = getTouchPosition(input)
            left.pad.Position = UDim2.fromOffset(left.center.X, left.center.Y)
            left.pad.Visible = true
            left.input = input
            moveStick(left, input)
            movementController.SetTouchMovement(left.axis, true)
        elseif not pinchLocked and #lookFingers < 2
            and cameraTouchZone(getTouchPosition(input))
            and not UiInputGuard.BlocksWorldInput(input, gameProcessed) then
            -- The former right-stick area remains invisible and fully usable.
            table.insert(lookFingers, input)
            lookPositions[input] = getTouchPosition(input)
            if #lookFingers == 2 then
                pinchLocked = true
                pinchGap = gapBetweenLookFingers()
            end
        end
    end)

    UserInputService.TouchMoved:Connect(function(input: InputObject)
        if input == left.input then
            moveStick(left, input)
            movementController.SetTouchMovement(left.axis, true)
            return
        end
        local previous = lookPositions[input]
        if not previous then
            return
        end
        local current = getTouchPosition(input)
        lookPositions[input] = current
        if #lookFingers == 1 and not pinchLocked then
            cameraController.RotateTouch(current - previous)
        elseif #lookFingers == 2 then
            local currentGap = gapBetweenLookFingers()
            if pinchGap and currentGap then
                cameraController.PinchZoom(pinchGap, currentGap)
            end
            pinchGap = currentGap
        end
    end)

    UserInputService.TouchEnded:Connect(function(input: InputObject)
        if input == left.input then
            releaseStick(left)
            movementController.SetTouchMovement(Vector2.zero, false)
            return
        end
        if not lookPositions[input] then
            return
        end
        lookPositions[input] = nil
        local index = table.find(lookFingers, input)
        if index then
            table.remove(lookFingers, index)
        end
        -- End the gesture only when ALL camera fingers are released. A remaining
        -- finger cannot keep zooming or rotating after a two-finger pinch.
        if #lookFingers == 0 then
            pinchLocked = false
            pinchGap = nil
        elseif #lookFingers < 2 then
            pinchGap = nil
        end
    end)

    UserInputService.WindowFocusReleased:Connect(resetTouch)
    jump.Activated:Connect(function()
        movementController.RequestJump()
    end)
    local function showAimState(selected: Model?)
        aim.BackgroundColor3 = if selected then Color3.fromRGB(27, 94, 101) else PALETTE.background
        aim.BackgroundTransparency = if selected then 0.10 else 0.48
    end
    cameraController.AutoAimChanged(showAimState)
    aim.Activated:Connect(function()
        cameraController.ToggleAutoAim()
    end)
    attack.Activated:Connect(function()
        if attackController.RequestAttack then
            attackController.RequestAttack()
        end
    end)
end

return MobileInputController
