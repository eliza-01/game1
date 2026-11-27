-- Global client contract: pointer input over visible UI never reaches world controls.
-- Decorative overlays may opt out explicitly with WorldInputPassthrough=true.
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")

local UiInputGuard = {}
local localPlayer = Players.LocalPlayer

local POINTER_TYPES = {
    [Enum.UserInputType.MouseButton1] = true,
    [Enum.UserInputType.MouseButton2] = true,
    [Enum.UserInputType.MouseButton3] = true,
    [Enum.UserInputType.MouseWheel] = true,
    [Enum.UserInputType.Touch] = true,
}

local function isPassthrough(object: Instance, playerGui: PlayerGui): boolean
    local current: Instance? = object
    while current and current ~= playerGui do
        if current:GetAttribute("WorldInputPassthrough") == true then
            return true
        end
        current = current.Parent
    end
    return false
end

function UiInputGuard.IsPointerOverUi(input: InputObject?): boolean
    local playerGui = localPlayer:FindFirstChildOfClass("PlayerGui")
    if not playerGui then
        return false
    end

    local inputType = input and input.UserInputType or Enum.UserInputType.MouseButton1
    if not POINTER_TYPES[inputType] then
        return false
    end

    local position: Vector2
    if input then
        position = Vector2.new(input.Position.X, input.Position.Y)
    else
        position = UserInputService:GetMouseLocation()
    end

    for _, object in ipairs(playerGui:GetGuiObjectsAtPosition(position.X, position.Y)) do
        if object.Visible and not isPassthrough(object, playerGui) then
            return true
        end
    end
    return false
end

-- World interaction actors may opt out of the primary attack click without
-- affecting camera drag or the normal pointer-over-UI policy.
function UiInputGuard.IsPointerOnWorldInteraction(): boolean
    local target = localPlayer:GetMouse().Target
    local model = target and target:FindFirstAncestorOfClass("Model")
    local character = localPlayer.Character
    if not model or not character then return false end
    local distance = model:GetAttribute("WorldInteractionDistance")
    if type(distance) ~= "number" or distance <= 0 then return false end
    local root = character:FindFirstChild("RootCollider")
    local other = model:FindFirstChild("RootCollider")
    return root ~= nil and root:IsA("BasePart") and other ~= nil and other:IsA("BasePart")
        and (root.Position - other.Position).Magnitude <= distance
end

function UiInputGuard.IsWorldSuspended(): boolean
    local gui = localPlayer:FindFirstChildOfClass("PlayerGui")
    return gui ~= nil and (gui:GetAttribute("Game1CharacterSceneInputBlocked") == true
        or gui:GetAttribute("Game1SettingsInputBlocked") == true)
end

function UiInputGuard.BlocksWorldInput(input: InputObject?, gameProcessed: boolean?): boolean
    if gameProcessed == true or UiInputGuard.IsWorldSuspended() then
        return true
    end
    if UserInputService:GetFocusedTextBox() ~= nil then
        return true
    end
    return UiInputGuard.IsPointerOverUi(input)
end

return table.freeze(UiInputGuard)
