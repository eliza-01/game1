--!strict
-- Live Studio-only camera preview; saved defaults always belong to GameOptions.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Players = game:GetService("Players")
local StudioDebugDock = require(script.Parent:WaitForChild("StudioDebugDock"))
local CameraController = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CameraController"))

local Debug = {}
local started = false
local FIELDS: {{key: string, label: string, step: number}} = {
    {key="targetHeight", label="Target height", step=0.25},
    {key="distance", label="Camera distance", step=0.25},
    {key="pitchDegrees", label="Pitch · °", step=1},
    {key="characterX", label="Character X · 0–1", step=0.02},
    {key="characterY", label="Character Y · 0–1", step=0.02},
    {key="cursorX", label="Cursor / aim X · 0–1", step=0.02},
    {key="cursorY", label="Cursor / aim Y · 0–1", step=0.02},
}
local COLORS = {bg=Color3.fromRGB(15,20,27), panel=Color3.fromRGB(25,34,44),
    text=Color3.fromRGB(238,243,246), muted=Color3.fromRGB(150,167,180),
    border=Color3.fromRGB(60,74,88), accent=Color3.fromRGB(76,217,184)}

local function button(parent: Instance, caption: string, width: number, height: number): TextButton
    local item=Instance.new("TextButton")
    item.Size=UDim2.fromOffset(width,height)
    item.Text=caption
    item.Font=Enum.Font.GothamSemibold
    item.TextSize=12
    item.TextColor3=COLORS.text
    item.BackgroundColor3=COLORS.panel
    item.Parent=parent
    local corner=Instance.new("UICorner")
    corner.CornerRadius=UDim.new(0,6)
    corner.Parent=item
    return item
end

function Debug.Start()
    if started or not RunService:IsStudio() then return end
    started=true
    local player=Players.LocalPlayer
    if not player then return end
    local gui=Instance.new("ScreenGui")
    gui.Name="Game1CameraDebug"
    gui.ResetOnSpawn=false
    gui.ZIndexBehavior=Enum.ZIndexBehavior.Global
    gui.Parent=player:WaitForChild("PlayerGui")
    local opener=button(gui,"CAM",44,44)
    opener.Position=StudioDebugDock.ButtonPosition("CD")
    opener.ZIndex=80
    opener:SetAttribute("DebugTooltip", "Camera debug")
    local panel=Instance.new("Frame")
    panel.Name="CameraDebugPanel"
    panel.Size=UDim2.fromOffset(362,404)
    panel.Position=StudioDebugDock.WindowPosition("CD",362)
    panel.BackgroundColor3=COLORS.bg
    panel.Visible=false
    panel.ZIndex=85
    panel.Parent=gui
    local corner=Instance.new("UICorner")
    corner.CornerRadius=UDim.new(0,10)
    corner.Parent=panel
    local border=Instance.new("UIStroke")
    border.Color=COLORS.border
    border.Parent=panel
    local heading=Instance.new("TextLabel")
    heading.Size=UDim2.fromOffset(265,32)
    heading.Position=UDim2.fromOffset(12,8)
    heading.BackgroundTransparency=1
    heading.TextColor3=COLORS.text
    heading.Font=Enum.Font.GothamSemibold
    heading.TextSize=13
    heading.TextXAlignment=Enum.TextXAlignment.Left
    heading.Text="CAMERA DEBUG · STUDIO"
    heading.ZIndex=86
    heading.Parent=panel
    local close=button(panel,"×",30,28)
    close.Position=UDim2.fromOffset(320,10)
    close.ZIndex=86
    local status=Instance.new("TextLabel")
    status.Size=UDim2.fromOffset(340,36)
    status.Position=UDim2.fromOffset(12,357)
    status.BackgroundTransparency=1
    status.TextColor3=COLORS.muted
    status.Font=Enum.Font.Gotham
    status.TextSize=11
    status.TextWrapped=true
    status.TextXAlignment=Enum.TextXAlignment.Left
    status.Text="Changes preview immediately; saved only in Control Center."
    status.ZIndex=86
    status.Parent=panel
    local values=CameraController.GetSettings()
    local fields: {[string]: TextBox} = {}
    local remoteFolder=ReplicatedStorage:WaitForChild("Game1Remotes",10)
    local remote=remoteFolder and remoteFolder:FindFirstChild("CameraDebugChanged")

    local function refresh()
        for key, field in fields do
            field.Text=string.format("%.3f", values[key])
        end
    end
    local function apply()
        if not CameraController.ApplyDebug(values) then
            status.Text="Invalid value. See the ranges in Camera Options."
            values=CameraController.GetSettings()
            refresh()
            return
        end
        if remote and remote:IsA("RemoteEvent") then
            remote:FireServer(values)
            status.Text="Preview active. Draft sent to Control Center · Save in Options."
        else
            status.Text="Preview active. CameraDebugChanged remote unavailable."
        end
    end
    for index, spec in ipairs(FIELDS) do
        local key,label,step=spec.key,spec.label,spec.step
        local y=44+(index-1)*43
        local t=Instance.new("TextLabel")
        t.Size=UDim2.fromOffset(171,31)
        t.Position=UDim2.fromOffset(12,y)
        t.Text=label
        t.Font=Enum.Font.Gotham
        t.TextColor3=COLORS.text
        t.TextSize=11
        t.TextXAlignment=Enum.TextXAlignment.Left
        t.BackgroundTransparency=1
        t.ZIndex=86
        t.Parent=panel
        local minus=button(panel,"−",29,29)
        minus.Position=UDim2.fromOffset(185,y)
        minus.ZIndex=86
        local entry=Instance.new("TextBox")
        entry.Size=UDim2.fromOffset(92,29)
        entry.Position=UDim2.fromOffset(216,y)
        entry.Font=Enum.Font.Code
        entry.TextSize=12
        entry.TextColor3=COLORS.text
        entry.BackgroundColor3=COLORS.panel
        entry.ClearTextOnFocus=false
        entry.ZIndex=86
        entry.Parent=panel
        local entryCorner=Instance.new("UICorner")
        entryCorner.CornerRadius=UDim.new(0,5)
        entryCorner.Parent=entry
        fields[key]=entry
        local plus=button(panel,"+",29,29)
        plus.Position=UDim2.fromOffset(310,y)
        plus.ZIndex=86
        minus.MouseButton1Click:Connect(function()
            values[key]=math.round((values[key]-step)*10000)/10000
            apply();refresh()
        end)
        plus.MouseButton1Click:Connect(function()
            values[key]=math.round((values[key]+step)*10000)/10000
            apply();refresh()
        end)
        entry.FocusLost:Connect(function(enterPressed)
            local parsed=tonumber(entry.Text)
            if parsed then values[key]=parsed end
            apply();refresh()
        end)
    end
    refresh()
    opener.MouseButton1Click:Connect(function()
        panel.Visible=not panel.Visible
        if panel.Visible then
            values=CameraController.GetSettings()
            refresh()
        end
    end)
    close.MouseButton1Click:Connect(function()panel.Visible=false end)
end

return table.freeze(Debug)
