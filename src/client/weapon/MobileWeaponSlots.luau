--!strict
-- Four fixed playtest category slots; the existing picker owns all equipment requests.
local GuiService = game:GetService("GuiService")
local Layout = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("mobile"):WaitForChild("MobileLayout"))
local ActionRegistry = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("mobile"):WaitForChild("MobileActionRegistry"))
local Slots = {}
local TYPES = {"dagger", "sword", "bigsword", "bow"}
local function line(parent: GuiObject, x: number, y: number, w: number, h: number, angle: number)
    local piece = Instance.new("Frame")
    piece.BackgroundColor3 = Color3.fromRGB(20, 35, 25)
    piece.BorderSizePixel = 0
    piece.AnchorPoint = Vector2.new(0.5, 0.5)
    piece.Position = UDim2.fromScale(x, y)
    piece.Size = UDim2.fromScale(w, h)
    piece.Rotation = angle
    piece.Parent = parent
end
function Slots.Create(gui: ScreenGui, choose: (string) -> ())
    local buttons: {[string]: TextButton} = {}
    for _, kind in ipairs(TYPES) do
        local button = Instance.new("TextButton")
        button.Name = "WeaponSlot_" .. kind
        button.AnchorPoint = Vector2.new(1, 0)
        button.Text = ""
        button.BorderSizePixel = 0
        button.BackgroundColor3 = Color3.fromRGB(169, 222, 46)
        button.BackgroundTransparency = 0.18
        button.Parent = gui
        local corner = Instance.new("UICorner")
        corner.CornerRadius = UDim.new(0, 7)
        corner.Parent = button
        if kind == "bow" then
            line(button,.48,.28,.09,.35,-35)
            line(button,.48,.72,.09,.35,35)
            line(button,.30,.50,.05,.65,0)
            line(button,.53,.50,.60,.06,0)
        else
            local blade = if kind == "dagger" then .34 elseif kind == "bigsword" then .64 else .50
            line(button,.58,.40,if kind == "bigsword" then .20 else .10,blade,45)
            line(button,.42,.57,.34,.08,45)
            line(button,.32,.70,.10,.25,45)
        end
        ActionRegistry.Register(button, "Weapon", function() choose(kind) end)
        buttons[kind] = button
    end
    local result = {}
    function result.Layout()
        -- Anchor in DeviceSafeInsets but measure using the combat HUD's
        -- CoreUISafeInsets rectangle, so the 37% Attack proportion is unchanged.
        local area = GuiService:GetInsetArea(Enum.ScreenInsets.CoreUISafeInsets)
        local size = area.Max - area.Min
        local box = Layout.Resolve(size.X, size.Y).weapon
        for i, kind in ipairs(TYPES) do
            local button = buttons[kind]
            button.Size = UDim2.fromOffset(box.size, box.size)
            button.Position = UDim2.new(1,-box.margin-((i-1)%2)*(box.size+box.gap),0,
                box.margin+math.floor((i-1)/2)*(box.size+box.gap))
        end
    end
    function result.SetSelected(kind: any)
        for key, button in pairs(buttons) do
            button.BackgroundTransparency = if key == kind then 0 else 0.32
        end
    end
    function result.SetVisible(visible: boolean)
        for _, button in pairs(buttons) do button.Visible = visible end
    end
    local insetConnection = GuiService:GetPropertyChangedSignal("TopbarInset"):Connect(result.Layout)
    gui.Destroying:Once(function() insetConnection:Disconnect() end)
    result.Layout()
    return result
end
return table.freeze(Slots)
