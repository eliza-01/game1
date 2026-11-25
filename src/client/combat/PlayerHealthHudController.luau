-- Player screen HP. Only local visual settings change; health is server-owned.
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local Settings = require(script.Parent:WaitForChild("HealthUiSettings"))

local Controller = {}
local player = Players.LocalPlayer
local started = false
local watched: Model? = nil
local connections: {RBXScriptConnection} = {}
local gui: ScreenGui? = nil
local plate: Frame? = nil
local border: UIStroke? = nil
local track: Frame? = nil
local fill: Frame? = nil
local caption: TextLabel? = nil
local progressionCaption: TextLabel? = nil
local effectsCaption: TextLabel? = nil
local tween: Tween? = nil
local first = true

local function color(hex: string): Color3
    return Color3.fromRGB(tonumber(hex:sub(2, 3), 16) or 255,
        tonumber(hex:sub(4, 5), 16) or 255, tonumber(hex:sub(6, 7), 16) or 255)
end

local function round(parent: Instance)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(1, 0)
    corner.Parent = parent
end

local function build(parent: PlayerGui)
    gui = Instance.new("ScreenGui")
    gui.Name = "Game1PlayerHealth"
    gui.DisplayOrder = 20
    gui.ResetOnSpawn = false
    gui.IgnoreGuiInset = true
    gui.Enabled = false
    gui.Parent = parent

    plate = Instance.new("Frame")
    plate.Name = "HealthTrack"
    plate.AnchorPoint = Vector2.new(0.5, 0)
    plate.BorderSizePixel = 0
    plate.BackgroundColor3 = Color3.fromRGB(12, 12, 15)
    plate.Parent = gui
    round(plate)
    border = Instance.new("UIStroke")
    border.Color = Color3.new(0, 0, 0)
    border.Parent = plate

    track = Instance.new("Frame")
    track.Name = "ClippedTrack"
    track.BackgroundColor3 = Color3.fromRGB(45, 33, 38)
    track.ClipsDescendants = true
    track.BorderSizePixel = 0
    track.Parent = plate
    round(track)

    fill = Instance.new("Frame")
    fill.Name = "Fill"
    fill.BorderSizePixel = 0
    fill.Size = UDim2.fromScale(1, 1)
    fill.Parent = track
    round(fill)
    local gradient = Instance.new("UIGradient")
    gradient.Rotation = 90
    gradient.Color = ColorSequence.new(Color3.new(1, 1, 1), Color3.fromRGB(224, 224, 224))
    gradient.Parent = fill

    caption = Instance.new("TextLabel")
    caption.Name = "HealthValue"
    caption.BackgroundTransparency = 1
    caption.Size = UDim2.fromScale(1, 1)
    caption.Font = Enum.Font.GothamBold
    caption.TextColor3 = Color3.new(1, 1, 1)
    caption.TextStrokeColor3 = Color3.new(0, 0, 0)
    caption.TextStrokeTransparency = 0
    caption.Parent = plate

    progressionCaption = Instance.new("TextLabel")
    progressionCaption.Name = "ProgressionValue"
    progressionCaption.BackgroundTransparency = 1
    progressionCaption.Position = UDim2.new(0, 0, 1, 2)
    progressionCaption.Size = UDim2.new(1, 0, 0, 18)
    progressionCaption.Font = Enum.Font.GothamBold
    progressionCaption.TextColor3 = Color3.new(1, 1, 1)
    progressionCaption.TextStrokeTransparency = 0.15
    progressionCaption.TextScaled = true
    local constraint = Instance.new("UITextSizeConstraint")
    constraint.MaxTextSize = 13
    constraint.Parent = progressionCaption
    progressionCaption.Parent = plate
    effectsCaption = Instance.new("TextLabel")
    effectsCaption.Name = "SkillEffects"; effectsCaption.BackgroundTransparency = 1
    effectsCaption.Position = UDim2.new(0,0,1,22); effectsCaption.Size = UDim2.new(1,0,0,18)
    effectsCaption.Font = Enum.Font.GothamBold; effectsCaption.TextColor3 = Color3.fromRGB(232,185,255)
    effectsCaption.TextStrokeTransparency = 0.15; effectsCaption.TextScaled = true; effectsCaption.Parent = plate
end
local function updateEffects()
    if not effectsCaption then return end
    effectsCaption.Text = if watched then tostring(watched:GetAttribute("ActiveSkillEffects") or "") else ""
    effectsCaption.Visible = effectsCaption.Text ~= ""
end

local function update()
    if not gui or not fill or not caption then return end
    local profile = Settings.Current()
    local model = watched
    if not model or not model.Parent then gui.Enabled = false; return end
    local maxHP = math.max(0, tonumber(model:GetAttribute("MaxHP")) or 0)
    local hp = math.clamp(tonumber(model:GetAttribute("HP")) or 0, 0, maxHP)
    local ratio = if maxHP > 0 then hp / maxHP else 0
    gui.Enabled = profile.screen.enabled and model:GetAttribute("LifeState") == "Alive" and maxHP > 0
    caption.Text = string.format("%d / %d", math.floor(hp + 0.5), math.floor(maxHP + 0.5))
    local palette = profile.colors
    local shade = if ratio <= 0.30 then palette.red elseif ratio <= 0.65 then palette.yellow else palette.green
    if tween then tween:Cancel(); tween = nil end
    local goal = {Size = UDim2.fromScale(ratio, 1), BackgroundColor3 = color(shade)}
    if first then
        fill.Size = goal.Size
        fill.BackgroundColor3 = goal.BackgroundColor3
        first = false
    else
        tween = TweenService:Create(fill, TweenInfo.new(0.23, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), goal)
        tween:Play()
    end
end

local function updateProgression()
    if not progressionCaption then return end
    local model = watched
    progressionCaption.Visible = model ~= nil and model:GetAttribute("XP") ~= nil
    if not model then return end
    local level = tonumber(model:GetAttribute("Level")) or 1
    local xp = tonumber(model:GetAttribute("XPIntoLevel")) or 0
    local nextXP = tonumber(model:GetAttribute("XPNext")) or 0
    local gold = tonumber(model:GetAttribute("Gold")) or 0
    progressionCaption.Text = if nextXP > 0 then string.format("LVL %d  ·  XP %d/%d  ·  G %d", level, xp, nextXP, gold)
        else string.format("LVL %d  ·  MAX  ·  G %d", level, gold)
end

local function applyStyle()
    if not plate or not border or not track or not caption then return end
    local spec = Settings.Current().screen
    plate.Position = UDim2.new(0.5, 0, 0, spec.top)
    plate.Size = UDim2.fromOffset(spec.width, spec.height)
    border.Thickness = spec.border
    local pad = math.min(3, math.max(1, math.floor(spec.height / 7)))
    track.Position = UDim2.fromOffset(pad, pad)
    track.Size = UDim2.new(1, -2 * pad, 1, -2 * pad)
    caption.TextSize = spec.textSize
    update()
end

local function bind(character: Model?)
    for _, connection in ipairs(connections) do connection:Disconnect() end
    table.clear(connections)
    if tween then tween:Cancel(); tween = nil end
    watched = character
    first = true
    if character then
        for _, key in ipairs({"HP", "MaxHP", "LifeState"}) do
            table.insert(connections, character:GetAttributeChangedSignal(key):Connect(update))
        end
        for _, key in ipairs({"Level", "XP", "XPIntoLevel", "XPNext", "Gold"}) do
            table.insert(connections, character:GetAttributeChangedSignal(key):Connect(updateProgression))
        end
    end
    if character then table.insert(connections,character:GetAttributeChangedSignal("ActiveSkillEffects"):Connect(updateEffects)) end
    update()
    updateProgression()
    updateEffects()
end

function Controller.Start()
    if started then return end
    started = true
    build(player:WaitForChild("PlayerGui"))
    Settings.Changed(applyStyle)
    applyStyle()
    player.CharacterAdded:Connect(bind)
    player.CharacterRemoving:Connect(function(character)
        if watched == character then bind(nil) end
    end)
    bind(player.Character)
end

return table.freeze(Controller)
