-- Gesture routing only. Custom physics, camera orbit and attacks retain their owners.
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")
local GuiService = game:GetService("GuiService")
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local Mobile = script.Parent:WaitForChild("mobile")
local View = require(Mobile:WaitForChild("MobileControlsView"))
local Layout = require(Mobile:WaitForChild("MobileLayout"))

local MobileInputController = {}
local started = false
local DEADZONE = 0.12

local function getTouchPosition(input: InputObject): Vector2
    return Vector2.new(input.Position.X, input.Position.Y)
end

function MobileInputController.Start(movementController: any, cameraController: any, attackController: any)
    if started or not UserInputService.TouchEnabled then return end
    started = true
    local player = Players.LocalPlayer
    local playerGui = player:WaitForChild("PlayerGui")
    local view = View.Create(playerGui)
    local gui = view.gui
    local left = {input = nil :: InputObject?, center = Vector2.zero, axis = Vector2.zero}
    local lookFingers: {InputObject} = {}
    local lookPositions: {[InputObject]: Vector2} = {}
    local cancellation: {[InputObject]: RBXScriptConnection} = {}
    local pinchGap: number? = nil
    local pinchLocked = false
    local menuOpen = GuiService.MenuIsOpen
    local character: Model? = nil
    local characterConnections: {RBXScriptConnection} = {}

    local function disconnectTouch(input: InputObject)
        local connection = cancellation[input]
        if connection then connection:Disconnect(); cancellation[input] = nil end
    end

    local function releaseStick()
        left.input = nil
        left.axis = Vector2.zero
        view.RestStick()
        movementController.SetTouchMovement(Vector2.zero, false)
    end

    local function resetTouch()
        for input, connection in cancellation do
            connection:Disconnect()
            cancellation[input] = nil
        end
        releaseStick()
        table.clear(lookFingers)
        table.clear(lookPositions)
        pinchGap = nil
        pinchLocked = false
    end

    local function active(): boolean
        return character ~= nil and character.Parent ~= nil
            and character:GetAttribute("LifeState") == "Alive"
            and not menuOpen and UserInputService:GetFocusedTextBox() == nil
    end

    local function refreshVisibility()
        local enabled = active()
        if not enabled then resetTouch() end
        gui.Enabled = enabled
    end

    local function bindCharacter(model: Model?)
        resetTouch()
        for _, connection in characterConnections do connection:Disconnect() end
        table.clear(characterConnections)
        character = model
        if model then
            local function refreshWeapon()
                view.SetWeapon(model:GetAttribute("EquippedWeaponType"))
            end
            refreshWeapon()
            table.insert(characterConnections, model:GetAttributeChangedSignal("EquippedWeaponType"):Connect(refreshWeapon))
            table.insert(characterConnections, model:GetAttributeChangedSignal("LifeState"):Connect(refreshVisibility))
        end
        refreshVisibility()
    end

    local function relayout()
        -- Insets or rotation can invalidate a finger's original coordinate system.
        resetTouch()
        view.Layout()
    end
    gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(relayout)
    gui:GetPropertyChangedSignal("AbsolutePosition"):Connect(relayout)
    player.CharacterAdded:Connect(bindCharacter)
    player.CharacterRemoving:Connect(function(model)
        if model == character then bindCharacter(nil) end
    end)
    bindCharacter(player.Character)

    local function gapBetweenLookFingers(): number?
        if #lookFingers ~= 2 then return nil end
        return (lookPositions[lookFingers[1]] - lookPositions[lookFingers[2]]).Magnitude
    end

    local function moveStick(input: InputObject)
        local delta = getTouchPosition(input) - left.center
        local magnitude = delta.Magnitude
        local normalized = if magnitude > view.radius then delta.Unit else delta / view.radius
        local strength = math.clamp((normalized.Magnitude - DEADZONE) / (1 - DEADZONE), 0, 1)
        local axis = if strength > 0 then Vector2.new(normalized.X, -normalized.Y).Unit * strength else Vector2.zero
        local thumbTravel = view.left.pad.Size.X.Offset * 0.27
        view.left.thumb.Position = UDim2.new(0.5, normalized.X * thumbTravel, 0.5, normalized.Y * thumbTravel)
        if axis ~= left.axis then
            left.axis = axis
            movementController.SetTouchMovement(left.axis, true)
        end
    end

    local function endTouch(input: InputObject)
        disconnectTouch(input)
        if input == left.input then releaseStick(); return end
        if not lookPositions[input] then return end
        lookPositions[input] = nil
        local index = table.find(lookFingers, input)
        if index then table.remove(lookFingers, index) end
        -- The survivor of a pinch is not a new drag gesture.
        if #lookFingers == 0 then
            pinchLocked = false
            pinchGap = nil
        elseif #lookFingers < 2 then
            pinchGap = nil
        end
    end

    local function watchCancellation(input: InputObject)
        cancellation[input] = input:GetPropertyChangedSignal("UserInputState"):Connect(function()
            if input.UserInputState == Enum.UserInputState.Cancel then endTouch(input) end
        end)
    end

    UserInputService.TouchStarted:Connect(function(input: InputObject, gameProcessed: boolean)
        if not active() or UiInputGuard.BlocksWorldInput(input, gameProcessed) then return end
        local position = getTouchPosition(input)
        local point = position - gui.AbsolutePosition
        local size = gui.AbsoluteSize
        if point.X < 0 or point.Y < 0 or point.X > size.X or point.Y > size.Y then return end
        -- First finger in the lower-left area owns the stick until release.
        if Layout.IsMoveZone(point.X, point.Y, size.X, size.Y) then
            if left.input then return end
            left.input = input
            left.center = position
            view.BeginStick(position)
            movementController.SetTouchMovement(left.axis, true)
            watchCancellation(input)
        elseif not pinchLocked and #lookFingers < 2 then
            table.insert(lookFingers, input)
            lookPositions[input] = position
            watchCancellation(input)
            if #lookFingers == 2 then
                pinchLocked = true
                pinchGap = gapBetweenLookFingers()
            end
        end
    end)

    UserInputService.TouchMoved:Connect(function(input: InputObject)
        if input == left.input then moveStick(input); return end
        local previous = lookPositions[input]
        if not previous then return end
        local current = getTouchPosition(input)
        if current == previous then return end
        lookPositions[input] = current
        if #lookFingers == 1 and not pinchLocked then
            cameraController.RotateTouch(current - previous)
        elseif #lookFingers == 2 then
            local currentGap = gapBetweenLookFingers()
            if pinchGap and currentGap then cameraController.PinchZoom(pinchGap, currentGap) end
            pinchGap = currentGap
        end
    end)
    UserInputService.TouchEnded:Connect(endTouch)
    UserInputService.WindowFocusReleased:Connect(resetTouch)
    UserInputService.TextBoxFocused:Connect(refreshVisibility)
    UserInputService.TextBoxFocusReleased:Connect(refreshVisibility)
    GuiService.MenuOpened:Connect(function() menuOpen = true; refreshVisibility() end)
    GuiService.MenuClosed:Connect(function() menuOpen = false; refreshVisibility() end)

    view.jump.Activated:Connect(function()
        if active() then movementController.RequestJump() end
    end)
    view.SetAim(cameraController.AutoAimTarget())
    cameraController.AutoAimChanged(view.SetAim)
    view.aim.Activated:Connect(function()
        if active() then cameraController.ToggleAutoAim() end
    end)
    view.attack.Activated:Connect(function()
        if active() and attackController.RequestAttack then attackController.RequestAttack() end
    end)
end

return MobileInputController
