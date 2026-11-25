-- Shared Studio-only debug toolbar coordinates. ScreenGui keeps the Roblox Core UI inset.
local Workspace = game:GetService("Workspace")

local StudioDebugDock = {}

local BUTTON_SIZE = 44
local BUTTON_GAP = 8
local LEFT = 16
local TOP = 8
local WINDOW_TOP = TOP + BUTTON_SIZE + BUTTON_GAP
local slots = { TL = 0, MV = 1, MO = 2, CS = 3, HS = 4, CD = 5, HP = 6, UI = 7, GP = 8 }
local SLOT_COUNT = 9
local STEP = BUTTON_SIZE + BUTTON_GAP
local CLOSED = Color3.fromRGB(28, 37, 48)
local SELECTED = Color3.fromRGB(31, 76, 70)
local TEXT = Color3.fromRGB(239, 244, 248)
local ACCENT = Color3.fromRGB(72, 214, 180)
local function availableWidth(): number
    local camera = Workspace.CurrentCamera
    return if camera then camera.ViewportSize.X else 0
end
local function columns(width: number): number
    if width <= 0 then return SLOT_COUNT end
    return math.clamp(math.floor((width - LEFT - 8 + BUTTON_GAP) / STEP), 1, SLOT_COUNT)
end

function StudioDebugDock.ButtonPosition(id: string, width: number?): UDim2
    local slot = assert(slots[id], "unknown debug panel: " .. id)
    local count = columns(width or availableWidth())
    return UDim2.fromOffset(LEFT + (slot % count) * STEP, TOP + math.floor(slot / count) * STEP)
end

function StudioDebugDock.WindowPosition(id: string, width: number, viewportWidth: number?): UDim2
    local viewport = viewportWidth or availableWidth()
    local desiredX = StudioDebugDock.ButtonPosition(id, viewport).X.Offset
    local x = if viewport > 0 then math.min(desiredX, math.max(8, viewport - width - 8)) else desiredX
    return UDim2.fromOffset(x, WINDOW_TOP + (math.ceil(SLOT_COUNT / columns(viewport)) - 1) * STEP)
end

-- Each launcher reflects its actual panel, never hover or initial construction.
-- ScreenGui size includes its inset; all slots reflow together when it changes.
function StudioDebugDock.Bind(id: string, launcher: TextButton, panel: GuiObject, width: number, adaptive: boolean?)
    local screen = launcher:FindFirstAncestorWhichIsA("ScreenGui") :: ScreenGui
    screen.DisplayOrder = 135 -- Above the game HUD, below character creation and language selection.
    launcher.Name = "DebugLauncher" .. id
    launcher.AutoButtonColor = false
    local function layout()
        local viewport = screen.AbsoluteSize.X
        launcher.Position = StudioDebugDock.ButtonPosition(id, viewport)
        local panelWidth = if adaptive then math.min(width, math.max(1, viewport - 16)) else width
        local position = StudioDebugDock.WindowPosition(id, panelWidth, viewport)
        panel.Position = position
        if adaptive then
            panel.Size = UDim2.fromOffset(panelWidth, math.max(1, math.min(585, screen.AbsoluteSize.Y - position.Y.Offset - 8)))
        end
    end
    local function paint()
        local open = panel.Visible and screen.Enabled
        launcher.BackgroundColor3 = if open then SELECTED else CLOSED
        launcher.TextColor3 = if open then ACCENT else TEXT
    end
    screen:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
    screen:GetPropertyChangedSignal("Enabled"):Connect(paint)
    panel:GetPropertyChangedSignal("Visible"):Connect(paint)
    layout(); paint()
end

StudioDebugDock.ButtonSize = BUTTON_SIZE
return StudioDebugDock
