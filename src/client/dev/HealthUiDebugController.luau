-- Studio Play-only live HP layout preview. Never persists gameplay state.
-- Edits are forwarded to the local Asset Manager as an importable draft.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local StudioDebugDock = require(script.Parent:WaitForChild("StudioDebugDock"))
local Settings = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("HealthUiSettings"))

local Debug = {}
local started = false
local BACKGROUND = Color3.fromRGB(15, 20, 27)
local RAISED = Color3.fromRGB(29, 39, 52)
local WHITE = Color3.fromRGB(239, 244, 248)
local MUTED = Color3.fromRGB(158, 178, 192)
local GREEN = Color3.fromRGB(72, 214, 180)
local LIMITS = {
    width={60,560,4}, height={6,60,1}, border={0,8,0.5},
    textSize={8,36,1}, nameSize={8,40,1}, levelSize={8,40,1},
    offsetStuds={0,12,0.25}, top={0,160,2}, maxDistanceStuds={20,800,10},
}
local GROUPS = {"screen", "self", "monster", "colors"}
local GROUP_NAMES = {screen="SCREEN", self="SELF", monster="MONSTER", colors="COLORS"}
local KEYS = {
    screen={"enabled", "width", "height", "border", "textSize", "top"},
    self={"enabled", "width", "height", "border", "nameSize", "levelSize", "offsetStuds"},
    monster={"enabled", "maxDistanceStuds", "width", "height", "border", "nameSize", "levelSize", "offsetStuds"},
    colors={"green", "yellow", "red"},
}

local function make(parent: Instance, kind: string, props: {[string]: any}): any
    local item = Instance.new(kind)
    for key, value in pairs(props) do (item :: any)[key] = value end
    item.Parent = parent
    return item
end
local function rounded(parent: Instance, pixels: number)
    make(parent, "UICorner", {CornerRadius=UDim.new(0,pixels)})
end
local function control(parent: Instance, title: string, w: number, h: number): TextButton
    local button = make(parent, "TextButton", {Text=title, Size=UDim2.fromOffset(w,h),
        BorderSizePixel=0, BackgroundColor3=RAISED, TextColor3=WHITE,
        Font=Enum.Font.GothamSemibold, TextSize=11})
    rounded(button, 6)
    return button
end
local function label(parent: Instance, name: string, x: number, y: number, w: number): TextLabel
    return make(parent, "TextLabel", {Text=name, BackgroundTransparency=1, TextColor3=WHITE,
        Position=UDim2.fromOffset(x,y), Size=UDim2.fromOffset(w,30),
        Font=Enum.Font.Gotham, TextSize=12, TextXAlignment=Enum.TextXAlignment.Left})
end
local function entry(parent: Instance, x: number, y: number): TextBox
    local field = make(parent, "TextBox", {Position=UDim2.fromOffset(x,y), Size=UDim2.fromOffset(89,30),
        ClearTextOnFocus=false, BackgroundColor3=RAISED, BorderSizePixel=0,
        TextColor3=WHITE, TextSize=12, Font=Enum.Font.Code})
    rounded(field, 6)
    return field
end
local function copy(value: any): any
    if type(value) ~= "table" then return value end
    local result = {}
    for k, v in pairs(value) do result[k] = copy(v) end
    return result
end
local function format(value: number): string
    return string.format("%.2f", value):gsub("0+$", ""):gsub("%.$", "")
end

function Debug.Start()
    if started or not RunService:IsStudio() then return end
    started = true
    local player = Players.LocalPlayer
    local gui = make(player:WaitForChild("PlayerGui"), "ScreenGui", {
        Name="Game1HealthUiDebug", ResetOnSpawn=false, DisplayOrder=31})
    local launcher = control(gui,"HP",44,44)
    launcher.Position = StudioDebugDock.ButtonPosition("HP")
    local panel = make(gui,"Frame", {Name="HealthUiDebugPanel", Visible=false,
        Size=UDim2.fromOffset(356,520), Position=StudioDebugDock.WindowPosition("HP",356),
        BackgroundColor3=BACKGROUND, BorderSizePixel=0})
    rounded(panel, 11)
    make(panel,"UIStroke", {Color=Color3.fromRGB(55,69,83),Thickness=1})
    label(panel,"HEALTH UI · LIVE STUDIO PREVIEW",14,8,300)
    local close = control(panel,"×",27,27); close.Position = UDim2.fromOffset(317,9)
    local deviceButtons = {}
    local groupButtons = {}
    local device = Settings.RuntimeDevice()
    local group = "monster"
    local drafts = {desktop=Settings.Saved("desktop"), mobile=Settings.Saved("mobile")}
    local rows = make(panel,"Frame", {Name="Rows", Position=UDim2.fromOffset(12,116),
        Size=UDim2.fromOffset(333,324), BackgroundTransparency=1})
    local status = label(panel,"Preview only · Save via Asset Manager Options",12,482,332)
    status.TextColor3 = MUTED
    status.TextSize = 10
    local reset = control(panel,"Reset selected profile",157,30)
    reset.Position = UDim2.fromOffset(12,448)
    local restore = control(panel,"Stop preview",153,30)
    restore.Position = UDim2.fromOffset(185,448)

    local remote: RemoteEvent? = nil
    task.spawn(function()
        local folder = ReplicatedStorage:WaitForChild("Game1Remotes", 12)
        local found = folder and folder:WaitForChild("HealthUiDebugChanged", 10)
        if found and found:IsA("RemoteEvent") then remote = found end
    end)
    local forwardRevision = 0
    local function forward()
        Settings.Preview(device, drafts[device])
        -- Debounce only transport; the UI preview changes immediately. This
        -- guarantees the last click wins even when the server rate-limits drafts.
        forwardRevision += 1
        local revision = forwardRevision
        local chosen = device
        local snapshot = copy(drafts[device])
        status.Text="Live preview · preparing Studio draft"
        task.delay(0.2, function()
            if revision ~= forwardRevision then return end
            if remote then
                remote:FireServer({device=chosen, settings=snapshot})
                status.Text="Live preview · Studio draft sent to Options"
            else
                status.Text="Live preview · draft connection unavailable"
            end
        end)
    end
    local render: () -> ()
    local function setValue(key: string, value: any)
        drafts[device][group][key] = value
        forward()
        render()
    end
    render = function()
        for _, item in ipairs(rows:GetChildren()) do item:Destroy() end
        for id, btn in pairs(deviceButtons) do
            btn.BackgroundColor3 = if id == device then GREEN else RAISED
            btn.TextColor3 = if id == device then BACKGROUND else WHITE
        end
        for id, btn in pairs(groupButtons) do
            btn.BackgroundColor3 = if id == group then GREEN else RAISED
            btn.TextColor3 = if id == group then BACKGROUND else WHITE
        end
        for index, key in ipairs(KEYS[group]) do
            local y = (index-1)*40
            local value = drafts[device][group][key]
            label(rows,key,0,y,113)
            if key == "enabled" then
                local toggle = control(rows, if value then "ON" else "OFF", 132,30)
                toggle.Position = UDim2.fromOffset(180,y)
                toggle.Activated:Connect(function() setValue(key,not value) end)
            else
                local minus = control(rows,"−",29,30); minus.Position=UDim2.fromOffset(114,y)
                local edit = entry(rows,150,y); edit.Text = if type(value)=="number" then format(value) else tostring(value)
                local plus = control(rows,"+",29,30); plus.Position=UDim2.fromOffset(250,y)
                if group=="colors" then
                    minus.Visible=false; plus.Visible=false
                    edit.Position=UDim2.fromOffset(151,y); edit.Size=UDim2.fromOffset(156,30)
                    edit.FocusLost:Connect(function()
                        local candidate = edit.Text:upper()
                        if candidate:match("^#%x%x%x%x%x%x$") then setValue(key,candidate)
                        else edit.Text=value; status.Text="Use #RRGGBB" end
                    end)
                else
                    local bounds=LIMITS[key]
                    local function setNumber(raw: any)
                        local parsed=tonumber(raw)
                        if not parsed or parsed ~= parsed then edit.Text=format(value); return end
                        setValue(key,math.clamp(parsed,bounds[1],bounds[2]))
                    end
                    minus.Activated:Connect(function() setNumber(value-bounds[3]) end)
                    plus.Activated:Connect(function() setNumber(value+bounds[3]) end)
                    edit.FocusLost:Connect(function() setNumber(edit.Text) end)
                end
            end
        end
    end
    for i, id in ipairs({"desktop","mobile"}) do
        local button = control(panel,if id=="desktop" then "PC" else "MOBILE",152,29)
        button.Position=UDim2.fromOffset(12+(i-1)*166,44)
        deviceButtons[id]=button
        button.Activated:Connect(function() device=id; render(); forward() end)
    end
    for i, id in ipairs(GROUPS) do
        local button = control(panel,GROUP_NAMES[id],75,28)
        button.Position=UDim2.fromOffset(12+(i-1)*83,81)
        groupButtons[id]=button
        button.Activated:Connect(function() group=id; render() end)
    end
    reset.Activated:Connect(function()
        drafts[device]=Settings.Saved(device)
        forward(); render()
    end)
    restore.Activated:Connect(function()
        Settings.ClearPreview()
        status.Text="Saved profile restored (no changes persisted)"
    end)
    launcher.Activated:Connect(function()
        panel.Visible=not panel.Visible
        if panel.Visible then render(); forward() end
    end)
    close.Activated:Connect(function() panel.Visible=false end)
    render()
end

return table.freeze(Debug)
