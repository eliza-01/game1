-- Shared Studio-only debug toolbar coordinates. ScreenGui keeps the Roblox Core UI inset.
local Workspace = game:GetService("Workspace")

local StudioDebugDock = {}

local BUTTON_SIZE = 44
local BUTTON_GAP = 8
local LEFT = 16
local TOP = 8
local WINDOW_TOP = TOP + BUTTON_SIZE + BUTTON_GAP
local slots = { TL = 0, MV = 1, MO = 2, CS = 3 }

function StudioDebugDock.ButtonPosition(id: string): UDim2
    local slot = assert(slots[id], "unknown debug panel: " .. id)
    return UDim2.fromOffset(LEFT + slot * (BUTTON_SIZE + BUTTON_GAP), TOP)
end

function StudioDebugDock.WindowPosition(id: string, width: number): UDim2
    local slot = assert(slots[id], "unknown debug panel: " .. id)
    local desiredX = LEFT + slot * (BUTTON_SIZE + BUTTON_GAP)
    local camera = Workspace.CurrentCamera
    local viewportWidth = if camera then camera.ViewportSize.X else 0
    local x = if viewportWidth > 0 then math.min(desiredX, math.max(8, viewportWidth - width - 8)) else desiredX
    return UDim2.fromOffset(x, WINDOW_TOP)
end

StudioDebugDock.ButtonSize = BUTTON_SIZE
return StudioDebugDock
