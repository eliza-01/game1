-- Shared Studio-only debug toolbar coordinates. ScreenGui keeps the Roblox Core UI inset.
local Workspace = game:GetService("Workspace")
local Input = game:GetService("UserInputService")
local Theme = require(script.Parent.Parent:WaitForChild("HudButtonTheme"))
local HudCornerLayout = require(script.Parent.Parent:WaitForChild("HudCornerLayout"))
local MobileLayout = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("mobile"):WaitForChild("MobileLayout"))

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Access = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Profile = require(script.Parent:WaitForChild("DebugDockProfile"))
local StudioDebugDock = {}
local Icons = require(script.Parent:WaitForChild("StudioDebugIcons"))

local BUTTON_SIZE = 44
local BUTTON_GAP = 8
local LEFT = HudCornerLayout.DebugLeft
local TOP = 8
local WINDOW_TOP = TOP + BUTTON_SIZE + BUTTON_GAP
local function profile()
    return Profile.Resolve(Input.TouchEnabled, Access.GameplayTestEnabled())
end
local STEP = BUTTON_SIZE + BUTTON_GAP
local CLOSED = Color3.fromRGB(28, 37, 48)
local SELECTED = Color3.fromRGB(31, 76, 70)
local TEXT = Color3.fromRGB(239, 244, 248)
local ACCENT = Color3.fromRGB(72, 214, 180)
local function availableWidth(): number
    local camera = Workspace.CurrentCamera
    return if camera then camera.ViewportSize.X else 0
end
local function columns(width: number, height: number?, slotCount: number): number
    if width <= 0 then return slotCount end
    local right = 8
    if Input.TouchEnabled then
        local camera = Workspace.CurrentCamera
        local weapon = MobileLayout.Resolve(width, height or (camera and camera.ViewportSize.Y) or width).weapon
        right = math.max(right, weapon.margin + 2*weapon.size + weapon.gap + BUTTON_GAP)
    end
    return HudCornerLayout.DebugColumns(width, right, BUTTON_SIZE, BUTTON_GAP, slotCount)
end

function StudioDebugDock.ButtonPosition(id: string, width: number?, height: number?): UDim2
    local active = profile()
    local slot = assert(active.slots[id], "inactive debug panel: " .. id)
    local count = columns(width or availableWidth(), height, active.count)
    return UDim2.fromOffset(LEFT + (slot % count) * STEP, TOP + math.floor(slot / count) * STEP)
end

function StudioDebugDock.WindowPosition(id: string, width: number, viewportWidth: number?, viewportHeight: number?): UDim2
    local viewport = viewportWidth or availableWidth()
    local desiredX = StudioDebugDock.ButtonPosition(id, viewport, viewportHeight).X.Offset
    local x = if viewport > 0 then math.min(desiredX, math.max(8, viewport - width - 8)) else desiredX
    return UDim2.fromOffset(x, WINDOW_TOP + (math.ceil(profile().count / columns(viewport, viewportHeight, profile().count)) - 1) * STEP)
end

-- Each launcher reflects its actual panel, never hover or initial construction.
-- ScreenGui size includes its inset; all slots reflow together when it changes.
function StudioDebugDock.Bind(id: string, launcher: TextButton, panel: GuiObject, width: number, adaptive: boolean?, bottomHeight: number?)
    local screen = launcher:FindFirstAncestorWhichIsA("ScreenGui") :: ScreenGui
    screen.DisplayOrder = 135 -- Above the game HUD, below character creation and language selection.
    launcher.Name = "DebugLauncher" .. id
    launcher.AutoButtonColor = false
    local paintIcon = Icons.Mount(id, launcher)
    local function layout()
        local viewport = screen.AbsoluteSize.X
        launcher.Position = StudioDebugDock.ButtonPosition(id, viewport, screen.AbsoluteSize.Y)
        local panelWidth = if adaptive then math.min(width, math.max(1, viewport - 16)) else width
        local position = StudioDebugDock.WindowPosition(id, panelWidth, viewport, screen.AbsoluteSize.Y)
        if bottomHeight then
            -- Bottom-left panels keep their bottom edge fixed as the viewport changes.
            panel.AnchorPoint = Vector2.new(0, 1)
            panel.Position = UDim2.new(0, 8, 1, -8)
            panel.Size = UDim2.fromOffset(panelWidth, math.max(1, math.min(bottomHeight, screen.AbsoluteSize.Y - position.Y.Offset - 16)))
        else
            panel.Position = position
        end
        if adaptive and not bottomHeight then
            panel.Size = UDim2.fromOffset(panelWidth, math.max(1, math.min(585, screen.AbsoluteSize.Y - position.Y.Offset - 8)))
        end
    end
    local function paint()
        local open = panel.Visible and screen.Enabled
        if Input.TouchEnabled then Theme.Apply(launcher)
        else launcher.BackgroundColor3 = if open then SELECTED else CLOSED end
        paintIcon(if open then ACCENT else TEXT)
    end
    screen:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
    screen:GetPropertyChangedSignal("Enabled"):Connect(paint)
    panel:GetPropertyChangedSignal("Visible"):Connect(paint)
    layout(); paint()
end

StudioDebugDock.ButtonSize = BUTTON_SIZE
return StudioDebugDock
