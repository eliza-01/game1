assert(plugin, "Этот код должен запускаться как Studio Plugin")

local Selection = game:GetService("Selection")
local Lighting = game:GetService("Lighting")
local UserInputService = game:GetService("UserInputService")
local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

-- ============================================================
-- PLUGIN WINDOW
-- ============================================================

local toolbar = plugin:CreateToolbar("Game1 Tools")

local toolbarButton = toolbar:CreateButton(
	"Fire Tuner",
	"Настройка огня и света на выбранной кости",
	""
)

toolbarButton.ClickableWhenViewportHidden = true

local widgetInfo = DockWidgetPluginGuiInfo.new(
	Enum.InitialDockState.Float,

	false, -- initially enabled
	false, -- remember previous state

	430,   -- default width
	720,   -- default height

	360,   -- minimum width
	420    -- minimum height
)

local widget = plugin:CreateDockWidgetPluginGuiAsync(
	"Game1_FireBoneTuner_v1",
	widgetInfo
)

widget.Title = "Fire Bone Tuner"

-- ============================================================
-- STATE
-- ============================================================

local currentBone = nil
local currentFire = nil
local currentLight = nil
local currentOrb = nil

local valueRefreshers = {}

-- ============================================================
-- COLORS
-- ============================================================

local BG = Color3.fromRGB(27, 27, 31)
local ROW = Color3.fromRGB(38, 38, 44)
local SECTION = Color3.fromRGB(47, 47, 54)
local BUTTON = Color3.fromRGB(61, 61, 69)

local TEXT = Color3.fromRGB(230, 230, 235)
local MUTED = Color3.fromRGB(160, 160, 170)
local VALUE = Color3.fromRGB(255, 205, 120)
local ACCENT = Color3.fromRGB(255, 155, 60)

-- ============================================================
-- ROOT
-- ============================================================

local root = Instance.new("Frame")
root.Size = UDim2.fromScale(1, 1)
root.BackgroundColor3 = BG
root.BorderSizePixel = 0
root.Parent = widget

-- ============================================================
-- HEADER
-- ============================================================

local header = Instance.new("Frame")
header.Size = UDim2.new(1, 0, 0, 92)
header.BackgroundColor3 = Color3.fromRGB(33, 33, 38)
header.BorderSizePixel = 0
header.Parent = root

local title = Instance.new("TextLabel")
title.Position = UDim2.fromOffset(12, 8)
title.Size = UDim2.new(1, -24, 0, 22)
title.BackgroundTransparency = 1
title.Text = "Fire Bone Tuner"
title.TextColor3 = TEXT
title.Font = Enum.Font.GothamBold
title.TextSize = 16
title.TextXAlignment = Enum.TextXAlignment.Left
title.Parent = header

local targetLabel = Instance.new("TextLabel")
targetLabel.Position = UDim2.fromOffset(12, 32)
targetLabel.Size = UDim2.new(1, -24, 0, 20)
targetLabel.BackgroundTransparency = 1
targetLabel.Text = "Target: none"
targetLabel.TextColor3 = MUTED
targetLabel.Font = Enum.Font.Code
targetLabel.TextSize = 11
targetLabel.TextXAlignment = Enum.TextXAlignment.Left
targetLabel.TextTruncate = Enum.TextTruncate.AtEnd
targetLabel.Parent = header

local selectButton = Instance.new("TextButton")
selectButton.Position = UDim2.fromOffset(12, 59)
selectButton.Size = UDim2.new(1, -24, 0, 26)
selectButton.BackgroundColor3 = ACCENT
selectButton.BorderSizePixel = 0
selectButton.Text = "USE SELECTED BONE"
selectButton.TextColor3 = Color3.new(1, 1, 1)
selectButton.Font = Enum.Font.GothamBold
selectButton.TextSize = 12
selectButton.Parent = header

local selectCorner = Instance.new("UICorner")
selectCorner.CornerRadius = UDim.new(0, 5)
selectCorner.Parent = selectButton

-- ============================================================
-- SCROLL
-- ============================================================

local scroll = Instance.new("ScrollingFrame")
scroll.Position = UDim2.fromOffset(8, 100)
scroll.Size = UDim2.new(1, -16, 1, -138)
scroll.BackgroundTransparency = 1
scroll.BorderSizePixel = 0
scroll.ScrollBarThickness = 6
scroll.AutomaticCanvasSize = Enum.AutomaticSize.Y
scroll.CanvasSize = UDim2.new()
scroll.Parent = root

local layout = Instance.new("UIListLayout")
layout.Padding = UDim.new(0, 4)
layout.SortOrder = Enum.SortOrder.LayoutOrder
layout.Parent = scroll

-- ============================================================
-- FOOTER
-- ============================================================

local footer = Instance.new("TextLabel")
footer.Position = UDim2.new(0, 10, 1, -32)
footer.Size = UDim2.new(1, -20, 0, 25)
footer.BackgroundTransparency = 1
footer.Text =
	"+/- normal  •  SHIFT ×10  •  ALT ×0.1  •  Time: SHIFT 1h / ALT 5m"

footer.TextColor3 = MUTED
footer.Font = Enum.Font.Gotham
footer.TextSize = 10
footer.TextWrapped = true
footer.Parent = root

-- ============================================================
-- HELPERS
-- ============================================================

local function rounded(frame, radius)
	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(0, radius or 5)
	corner.Parent = frame
end

local function getStep(base)

	local shift =
		UserInputService:IsKeyDown(Enum.KeyCode.LeftShift)
		or UserInputService:IsKeyDown(Enum.KeyCode.RightShift)

	local alt =
		UserInputService:IsKeyDown(Enum.KeyCode.LeftAlt)
		or UserInputService:IsKeyDown(Enum.KeyCode.RightAlt)

	if shift and not alt then
		return base * 10
	end

	if alt and not shift then
		return base * 0.1
	end

	return base
end

local function refreshAll()

	for _, callback in ipairs(valueRefreshers) do
		callback()
	end
end

local function addSection(name)

	local section = Instance.new("TextLabel")
	section.Size = UDim2.new(1, -4, 0, 30)
	section.BackgroundColor3 = SECTION
	section.BorderSizePixel = 0
	section.Text = "  " .. name
	section.TextColor3 = ACCENT
	section.Font = Enum.Font.GothamBold
	section.TextSize = 13
	section.TextXAlignment = Enum.TextXAlignment.Left
	section.Parent = scroll

	rounded(section)
end

-- ============================================================
-- NUMBER ROW
-- ============================================================

local function addNumber(
	name,
	getter,
	setter,
	step,
	minimum,
	maximum,
	format
)

	local row = Instance.new("Frame")
	row.Size = UDim2.new(1, -4, 0, 34)
	row.BackgroundColor3 = ROW
	row.BorderSizePixel = 0
	row.Parent = scroll
	rounded(row)

	local label = Instance.new("TextLabel")
	label.Position = UDim2.fromOffset(8, 0)
	label.Size = UDim2.new(0.42, -8, 1, 0)
	label.BackgroundTransparency = 1
	label.Text = name
	label.TextColor3 = TEXT
	label.Font = Enum.Font.Gotham
	label.TextSize = 12
	label.TextXAlignment = Enum.TextXAlignment.Left
	label.Parent = row

	local minus = Instance.new("TextButton")
	minus.AnchorPoint = Vector2.new(1, 0.5)
	minus.Position = UDim2.new(0.58, 0, 0.5, 0)
	minus.Size = UDim2.fromOffset(30, 24)
	minus.BackgroundColor3 = BUTTON
	minus.BorderSizePixel = 0
	minus.Text = "−"
	minus.TextColor3 = TEXT
	minus.Font = Enum.Font.GothamBold
	minus.TextSize = 16
	minus.Parent = row
	rounded(minus, 4)

	local value = Instance.new("TextLabel")
	value.AnchorPoint = Vector2.new(0, 0.5)
	value.Position = UDim2.new(0.59, 0, 0.5, 0)
	value.Size = UDim2.new(0.25, 0, 0, 24)
	value.BackgroundColor3 = Color3.fromRGB(25, 25, 29)
	value.BorderSizePixel = 0
	value.TextColor3 = VALUE
	value.Font = Enum.Font.Code
	value.TextSize = 12
	value.Parent = row
	rounded(value, 4)

	local plus = Instance.new("TextButton")
	plus.AnchorPoint = Vector2.new(1, 0.5)
	plus.Position = UDim2.new(1, -7, 0.5, 0)
	plus.Size = UDim2.fromOffset(30, 24)
	plus.BackgroundColor3 = BUTTON
	plus.BorderSizePixel = 0
	plus.Text = "+"
	plus.TextColor3 = TEXT
	plus.Font = Enum.Font.GothamBold
	plus.TextSize = 15
	plus.Parent = row
	rounded(plus, 4)

	local function refresh()

		local ok, v = pcall(getter)

		if not ok or v == nil then
			value.Text = "—"
			return
		end

		value.Text =
			format
			and string.format(format, v)
			or tostring(v)
	end

	table.insert(valueRefreshers, refresh)

	local function change(direction)

		if not currentBone then
			return
		end

        local ok, current = pcall(getter)
        if not ok or type(current) ~= "number" then return end
		local newValue =
			current + getStep(step) * direction

		if minimum ~= nil then
			newValue = math.max(minimum, newValue)
		end

		if maximum ~= nil then
			newValue = math.min(maximum, newValue)
		end

		setter(newValue)
		refresh()
	end

	minus.MouseButton1Click:Connect(function()
		change(-1)
	end)

	plus.MouseButton1Click:Connect(function()
		change(1)
	end)

	refresh()
end

-- ============================================================
-- TOGGLE
-- ============================================================

local function addToggle(name, getter, setter)

	local row = Instance.new("Frame")
	row.Size = UDim2.new(1, -4, 0, 34)
	row.BackgroundColor3 = ROW
	row.BorderSizePixel = 0
	row.Parent = scroll
	rounded(row)

	local label = Instance.new("TextLabel")
	label.Position = UDim2.fromOffset(8, 0)
	label.Size = UDim2.new(0.65, 0, 1, 0)
	label.BackgroundTransparency = 1
	label.Text = name
	label.TextColor3 = TEXT
	label.Font = Enum.Font.Gotham
	label.TextSize = 12
	label.TextXAlignment = Enum.TextXAlignment.Left
	label.Parent = row

	local button = Instance.new("TextButton")
	button.AnchorPoint = Vector2.new(1, 0.5)
	button.Position = UDim2.new(1, -8, 0.5, 0)
	button.Size = UDim2.fromOffset(80, 24)
	button.BorderSizePixel = 0
	button.TextColor3 = TEXT
	button.Font = Enum.Font.GothamBold
	button.TextSize = 11
	button.Parent = row
	rounded(button, 4)

	local function refresh()

		if not currentBone then
			button.Text = "—"
			button.BackgroundColor3 = BUTTON
			return
		end

        local ok, enabled = pcall(getter)
        if not ok or type(enabled) ~= "boolean" then
            button.Text = "—"; button.BackgroundColor3 = BUTTON; return
        end

		button.Text =
			enabled and "ON" or "OFF"

		button.BackgroundColor3 =
			enabled
			and Color3.fromRGB(55, 115, 65)
			or Color3.fromRGB(100, 55, 55)
	end

	table.insert(valueRefreshers, refresh)

	button.MouseButton1Click:Connect(function()

		if not currentBone then
			return
		end

        local ok, enabled = pcall(getter)
        if not ok or type(enabled) ~= "boolean" then return end
        setter(not enabled)
		refresh()
	end)

	refresh()
end

-- ============================================================
-- COLOR CHANNEL
-- ============================================================

local function addColorChannel(
	name,
	objectGetter,
	property,
	channel
)

	addNumber(
		name,

		function()

			local object = objectGetter()

            if not object then return nil end

			local c = object[property]

			if channel == "R" then
				return math.round(c.R * 255)
			elseif channel == "G" then
				return math.round(c.G * 255)
			else
				return math.round(c.B * 255)
			end
		end,

		function(value)

			local object = objectGetter()

			if not object then
				return
			end

			local c = object[property]

			local r = math.round(c.R * 255)
			local g = math.round(c.G * 255)
			local b = math.round(c.B * 255)

			value =
				math.clamp(
					math.round(value),
					0,
					255
				)

			if channel == "R" then
				r = value
			elseif channel == "G" then
				g = value
			else
				b = value
			end

			object[property] =
				Color3.fromRGB(r, g, b)
		end,

		10, -- normal ±10; ALT = 1; SHIFT = 100
		0,
		255,
		"%d"
	)
end

-- ============================================================
-- BIND SELECTED BONE
-- ============================================================

-- Selecting a Bone is a read-only inspection, NEVER an effect creation.
-- Only explicit Create / preset actions may author new instances.
local function findEffect(bone: Bone, className: string): Instance?
    local effect = bone:FindFirstChildOfClass(className)
    if effect then return effect end
    for _, child in ipairs(bone:GetChildren()) do
        if child:IsA("Attachment") then
            local nested = child:FindFirstChildOfClass(className)
            if nested then return nested end
        end
    end
    return nil
end

local function createFire()
    if not currentBone or currentFire then return end
    local axis = currentBone:FindFirstChild("Game1FireDirection")
    if axis and not axis:IsA("Attachment") then
        warn("Game1FireDirection must be an Attachment"); return
    end
    if not axis then
        axis = Instance.new("Attachment")
        axis.Name = "Game1FireDirection"
        -- Native Fire emits along local +Y. Preserve original Tail -> Head
        -- direction from the authored Bone; existing effects are never flipped.
        axis.CFrame = CFrame.Angles(math.pi, 0, 0)
        axis.Parent = currentBone
    end
    local fire = Instance.new("Fire")
    fire.Name = "FireFX"
    fire.Size = 4
    fire.Heat = 8
    fire.Color = Color3.fromRGB(255, 170, 65)
    fire.SecondaryColor = Color3.fromRGB(255, 70, 20)
    fire.Parent = axis
    currentFire = fire
    refreshAll()
end

local function createLight()
    if not currentBone or currentLight then return end
    local light = Instance.new("PointLight")
    light.Name = "FireLight"
    light.Brightness = 2
    light.Range = 18
    light.Color = Color3.fromRGB(255, 145, 70)
    light.Parent = currentBone
    currentLight = light
    refreshAll()
end

local function createFirefly()
    if not currentBone then return end
    local effect = currentOrb
    if not effect then
        effect = Instance.new("Attachment")
        effect.Name = "Game1OrbEffect"
        -- Defaults apply ONLY after the explicit Create Firefly action.
        effect:SetAttribute("Enabled", true)
        effect:SetAttribute("Color", Color3.fromRGB(255, 224, 145))
        effect:SetAttribute("Radius", 0.22)
        effect:SetAttribute("Brightness", 1.65)
        effect:SetAttribute("Range", 33.5)
        effect:SetAttribute("Shadows", false)
        effect:SetAttribute("Lift", 0.4)
        effect:SetAttribute("BobAmplitude", 0.12)
        effect:SetAttribute("BobFrequency", 0.35)
        effect:SetAttribute("Drift", 0.08)
        effect:SetAttribute("RoamRadius", 0.8)
        effect:SetAttribute("RoamSpeed", 0.5)
        effect.Parent = currentBone
        currentOrb = effect
    end
    if not CollectionService:HasTag(effect, "Game1LightOrb") then
        CollectionService:AddTag(effect, "Game1LightOrb")
    end
    refreshAll()
end

-- ============================================================
-- FIREFLY LIVE PREVIEW · Studio Edit only
-- Preview instances are not authored assets, not tagged and never published.
-- The client BoneOrbController remains the sole in-game renderer.
-- ============================================================
local previewEnabled = true
local previewPart: BasePart? = nil
local previewPhase = 1.17
local previewSeed = math.random(1, 100000)
local previewHint: TextLabel? = nil
local PREVIEW_NAME = "Game1FireTunerFireflyPreview"

local function discardPreview()
    if previewPart then
        previewPart:Destroy()
        previewPart = nil
    end
end

local function setPreviewHint(text: string)
    if previewHint and previewHint.Text ~= text then
        previewHint.Text = text
    end
end

local function hasPreviewTarget(): boolean
    return previewEnabled and widget.Enabled and RunService:IsEdit()
        and currentBone ~= nil and currentBone:IsDescendantOf(Workspace)
        and currentOrb ~= nil and currentOrb:IsA("Attachment")
        and currentOrb.Parent == currentBone
        and currentOrb:GetAttribute("Enabled") == true
end

local function getPreviewPart(): BasePart?
    local camera = Workspace.CurrentCamera
    if not camera then return nil end
    if previewPart and previewPart.Parent == camera then return previewPart end
    discardPreview()

    -- Archivable=false prevents this editor-only visualization being saved
    -- in the place, even if Studio saves while the preview is active.
    local part = Instance.new("Part")
    part.Name = PREVIEW_NAME
    part.Archivable = false
    part.Shape = Enum.PartType.Ball
    part.Material = Enum.Material.Neon
    part.Anchored = true
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = false
    part.CastShadow = false
    part.Locked = true
    local light = Instance.new("PointLight")
    light.Name = "PreviewPointLight"
    light.Archivable = false
    light.Parent = part
    part.Parent = camera
    previewPart = part
    return part
end

local function updatePreview(dt: number)
    if not hasPreviewTarget() then
        discardPreview()
        if not widget.Enabled then
            setPreviewHint("Open Fire Tuner to preview in Studio Edit")
        elseif not RunService:IsEdit() then
            setPreviewHint("Preview paused in Play; game controls Firefly")
        elseif not previewEnabled then
            setPreviewHint("Preview off · effects untouched")
        elseif not currentBone then
            setPreviewHint("Use Selected Bone to inspect its Firefly")
        else
            setPreviewHint("No enabled Firefly · create or enable it above")
        end
        return
    end
    local part = getPreviewPart()
    if not part then
        setPreviewHint("No Studio camera available")
        return
    end
    local orb = currentOrb :: Attachment
    local bone = currentBone :: Bone
    -- Match the existing BoneOrbController placement and attribute limits.
    local frame = bone.TransformedWorldCFrame * orb.CFrame
    local t = os.clock() * math.pi * 2
        * math.clamp(tonumber(orb:GetAttribute("BobFrequency")) or 0.35, 0, 3)
        + previewPhase
    local pos = frame.Position + Vector3.yAxis * (
        math.clamp(tonumber(orb:GetAttribute("Lift")) or 0.4, -3, 6)
        + math.sin(t) * math.clamp(tonumber(orb:GetAttribute("BobAmplitude")) or 0.12, 0, 2))
        + frame.RightVector * math.sin(t * 0.73)
        * math.clamp(tonumber(orb:GetAttribute("Drift")) or 0.08, 0, 2)
    local roamRadius = math.clamp(tonumber(orb:GetAttribute("RoamRadius")) or 0, 0, 10)
    if roamRadius > 0 then
        local speed = math.clamp(tonumber(orb:GetAttribute("RoamSpeed")) or 0.5, 0.05, 3)
        local sampleTime = os.clock() * speed * 0.4
        local seed = previewSeed
        pos += Vector3.new(
            math.noise(seed, sampleTime, 0),
            math.noise(seed, sampleTime, 17),
            math.noise(seed, sampleTime, 37)
        ) * roamRadius
    end
    local radius = math.clamp(tonumber(orb:GetAttribute("Radius")) or 0.22, 0.06, 1.5)
    part.Size = Vector3.new(radius * 2, radius * 2, radius * 2)
    part.Position = pos
    local color = orb:GetAttribute("Color")
    part.Color = if typeof(color) == "Color3" then color else Color3.fromRGB(255, 224, 145)
    local light = part:FindFirstChildOfClass("PointLight")
    if light then
        light.Color = part.Color
        light.Brightness = math.clamp(tonumber(orb:GetAttribute("Brightness")) or 1.65, 0, 8)
        light.Range = math.clamp(tonumber(orb:GetAttribute("Range")) or 33.5, 0, 60)
        light.Shadows = orb:GetAttribute("Shadows") == true
    end
    setPreviewHint("LIVE · Edit preview, not saved with the place")
end

local previewAccumulator = 0
local previewConnection = RunService.Heartbeat:Connect(function(dt)
    if not hasPreviewTarget() then
        updatePreview(0)
        previewAccumulator = 0
        return
    end
    previewAccumulator += dt
    if previewAccumulator < 1 / 30 then return end
    previewAccumulator %= 1 / 30
    updatePreview(dt)
end)

local function addExplicitCreate(labelText: string, action)
    local button = Instance.new("TextButton")
    button.Size = UDim2.new(1, -4, 0, 30)
    button.Text = labelText
    button.BackgroundColor3 = BUTTON
    button.TextColor3 = TEXT
    button.Font = Enum.Font.GothamSemibold
    button.TextSize = 11
    button.Parent = scroll
    rounded(button)
    button.MouseButton1Click:Connect(action)
end

local function bindSelected()
    local selected = Selection:Get()
    if #selected ~= 1 or not selected[1]:IsA("Bone") then
        warn("Select exactly one Bone")
        return
    end
    currentBone = selected[1]
    currentFire = findEffect(currentBone, "Fire")
    currentLight = findEffect(currentBone, "PointLight")
    currentOrb = currentBone:FindFirstChild("Game1OrbEffect")
    if currentOrb and not currentOrb:IsA("Attachment") then currentOrb = nil end
    targetLabel.Text = "Target: " .. currentBone:GetFullName()
        .. (if currentFire or currentLight then " · existing effects" else " · no effects")
    refreshAll()
end

selectButton.MouseButton1Click:Connect(
	bindSelected
)

-- ============================================================
-- FIRE TUNER PRESETS (plugin settings only; per-rig Fire FX remain authored)
-- The source archive did not contain the user's former custom presets.
-- Never replace old settings with a builtin profile on startup.
-- ============================================================

local PRESET_KEY = "Game1_FireTuner_UserPresets_v1"
local builtin = {
    {name = "Torch · warm", fire = {enabled = true, size = 4, heat = 8, timeScale = 1,
        color = {255, 170, 65}, secondary = {255, 70, 20}},
        light = {enabled = true, shadows = false, brightness = 2, range = 18, color = {255, 145, 70}}},
    {name = "Candle · soft", fire = {enabled = true, size = 1.2, heat = 3, timeScale = 0.65,
        color = {255, 199, 105}, secondary = {255, 110, 32}},
        light = {enabled = true, shadows = false, brightness = 0.7, range = 9, color = {255, 174, 98}}},
    {name = "Blue · mystic", fire = {enabled = true, size = 3, heat = 6, timeScale = 0.8,
        color = {75, 180, 255}, secondary = {32, 110, 245}},
        light = {enabled = true, shadows = false, brightness = 1.5, range = 15, color = {73, 154, 255}}},
}
local loaded = plugin:GetSetting(PRESET_KEY)
local userPresets = if typeof(loaded) == "table" then loaded else {}
local function rgb(color)
    return {math.round(color.R * 255), math.round(color.G * 255), math.round(color.B * 255)}
end
local function fromRgb(values)
    if type(values) ~= "table" or #values ~= 3 then return nil end
    for _, v in ipairs(values) do
        if type(v) ~= "number" or v ~= v then return nil end
    end
    return Color3.fromRGB(math.clamp(values[1], 0, 255), math.clamp(values[2], 0, 255), math.clamp(values[3], 0, 255))
end
local function capturePreset(name)
    return {name = name, fire = currentFire and {
        enabled = currentFire.Enabled, size = currentFire.Size, heat = currentFire.Heat,
        timeScale = currentFire.TimeScale, color = rgb(currentFire.Color),
        secondary = rgb(currentFire.SecondaryColor),
    } or nil, light = currentLight and {
        enabled = currentLight.Enabled, shadows = currentLight.Shadows,
        brightness = currentLight.Brightness, range = currentLight.Range,
        color = rgb(currentLight.Color),
    } or nil, orb = currentOrb and {
        enabled = currentOrb:GetAttribute("Enabled") == true,
        radius = currentOrb:GetAttribute("Radius"),
        brightness = currentOrb:GetAttribute("Brightness"),
        range = currentOrb:GetAttribute("Range"),
        lift = currentOrb:GetAttribute("Lift"),
        bobAmplitude = currentOrb:GetAttribute("BobAmplitude"),
        bobFrequency = currentOrb:GetAttribute("BobFrequency"),
        drift = currentOrb:GetAttribute("Drift"),
        roamRadius = currentOrb:GetAttribute("RoamRadius"),
        roamSpeed = currentOrb:GetAttribute("RoamSpeed"),
        shadows = currentOrb:GetAttribute("Shadows") == true,
        color = rgb(currentOrb:GetAttribute("Color") or Color3.new(1, 1, 1)),
    } or nil}
end
local function applyPreset(data)
    if not currentBone or type(data) ~= "table" then return end
    local fire, light = data.fire, data.light
    if type(fire) == "table" then
        if not currentFire then createFire() end
        if not currentFire then return end
    currentFire.Enabled = fire.enabled == true
    currentFire.Size = math.clamp(tonumber(fire.size) or currentFire.Size, 0, 30)
    currentFire.Heat = math.clamp(tonumber(fire.heat) or currentFire.Heat, -25, 25)
    currentFire.TimeScale = math.clamp(tonumber(fire.timeScale) or currentFire.TimeScale, 0, 1)
    currentFire.Color = fromRgb(fire.color) or currentFire.Color
    currentFire.SecondaryColor = fromRgb(fire.secondary) or currentFire.SecondaryColor
    end
    if type(light) == "table" then
        if not currentLight then createLight() end
        if not currentLight then return end
    currentLight.Enabled = light.enabled == true
    currentLight.Shadows = light.shadows == true
    currentLight.Brightness = math.clamp(tonumber(light.brightness) or currentLight.Brightness, 0, 20)
    currentLight.Range = math.clamp(tonumber(light.range) or currentLight.Range, 0, 60)
    currentLight.Color = fromRgb(light.color) or currentLight.Color
    end
    if type(data.orb) == "table" then
        createFirefly() -- explicit preset application also registers an existing effect
        if not currentOrb then return end
        local o = data.orb
        currentOrb:SetAttribute("Enabled", o.enabled == true)
        for attribute, key in pairs({Radius="radius", Brightness="brightness", Range="range",
            Lift="lift", BobAmplitude="bobAmplitude", BobFrequency="bobFrequency", Drift="drift",
            RoamRadius="roamRadius", RoamSpeed="roamSpeed"}) do
            local value = tonumber(o[key])
            if value and value == value then currentOrb:SetAttribute(attribute, value) end
        end
        currentOrb:SetAttribute("Color", fromRgb(o.color) or currentOrb:GetAttribute("Color"))
        if type(o.shadows) == "boolean" then currentOrb:SetAttribute("Shadows", o.shadows) end
    end
    refreshAll()
end

addSection("PRESETS · FIRE / LIGHT / ORB")
local presetRow = Instance.new("Frame")
presetRow.Size = UDim2.new(1, -4, 0, 70)
presetRow.BackgroundTransparency = 1
presetRow.Parent = scroll
local presetName = Instance.new("TextBox")
presetName.Size = UDim2.new(1, -8, 0, 28)
presetName.Position = UDim2.fromOffset(4, 0)
presetName.PlaceholderText = "Preset name (for saving your own)"
presetName.Text = ""
presetName.ClearTextOnFocus = false
presetName.TextColor3 = TEXT
presetName.BackgroundColor3 = ROW
presetName.Parent = presetRow
rounded(presetName)
local presetActionRow = Instance.new("Frame")
presetActionRow.BackgroundTransparency = 1
presetActionRow.Size = UDim2.new(1, 0, 0, 32)
presetActionRow.Position = UDim2.fromOffset(0, 34)
presetActionRow.Parent = presetRow
local function presetButton(text, x, width)
    local button = Instance.new("TextButton")
    button.Size = UDim2.new(width, -4, 1, 0)
    button.Position = UDim2.fromScale(x, 0)
    button.Text = text
    button.TextColor3 = TEXT
    button.BackgroundColor3 = BUTTON
    button.Font = Enum.Font.GothamBold
    button.TextSize = 11
    button.Parent = presetActionRow
    rounded(button)
    return button
end
local savePreset = presetButton("Save current", 0, 0.5)
local removePreset = presetButton("Delete selected", 0.5, 0.5)
local presetChoices = Instance.new("Frame")
presetChoices.Size = UDim2.new(1, -4, 0, 0)
presetChoices.AutomaticSize = Enum.AutomaticSize.Y
presetChoices.BackgroundTransparency = 1
presetChoices.Parent = scroll
local choiceLayout = Instance.new("UIListLayout")
choiceLayout.SortOrder = Enum.SortOrder.LayoutOrder
choiceLayout.Padding = UDim.new(0, 4)
choiceLayout.Parent = presetChoices
local selectedPresetName = ""
local function showPresets()
    for _, node in ipairs(presetChoices:GetChildren()) do
        if node:IsA("TextButton") then node:Destroy() end
    end
    local all = {}
    for _, value in ipairs(builtin) do table.insert(all, value) end
    for _, value in ipairs(userPresets) do
        if type(value) == "table" and type(value.name) == "string" then table.insert(all,value) end
    end
    for index, value in ipairs(all) do
        local button = Instance.new("TextButton")
        button.LayoutOrder = index
        button.Size = UDim2.new(1, 0, 0, 27)
        button.Text = value.name
        button.TextXAlignment = Enum.TextXAlignment.Left
        button.TextColor3 = TEXT
        button.BackgroundColor3 = if selectedPresetName == value.name then ACCENT else ROW
        button.TextSize = 12
        button.Parent = presetChoices
        rounded(button)
        button.MouseButton1Click:Connect(function()
            if not currentBone then warn("Select a Bone first"); return end
            selectedPresetName = value.name
            presetName.Text = value.name
            applyPreset(value)
            showPresets()
        end)
    end
end
savePreset.MouseButton1Click:Connect(function()
    if not currentBone then warn("Select a Bone first"); return end
    local name = presetName.Text:match("^%s*(.-)%s*$")
    if #name < 1 or #name > 48 then warn("Preset name must have 1–48 characters"); return end
    for _, entry in ipairs(builtin) do
        if entry.name == name then warn("Builtin preset cannot be overwritten"); return end
    end
    if not currentFire and not currentLight and not currentOrb then warn("No effects on this Bone to save"); return end
    local data = capturePreset(name)
    for i = #userPresets, 1, -1 do
        if userPresets[i].name == name then table.remove(userPresets, i) end
    end
    table.insert(userPresets, data)
    plugin:SetSetting(PRESET_KEY, userPresets)
    selectedPresetName = name
    showPresets()
end)
removePreset.MouseButton1Click:Connect(function()
    if selectedPresetName == "" then return end
    for i = #userPresets, 1, -1 do
        if userPresets[i].name == selectedPresetName then table.remove(userPresets, i) end
    end
    plugin:SetSetting(PRESET_KEY, userPresets)
    selectedPresetName = ""
    showPresets()
end)
showPresets()

-- ============================================================
-- FIRE
-- ============================================================

addSection("FIRE")
addExplicitCreate("Create Fire on selected Bone", createFire)

addToggle(
	"Enabled",

	function()
		return currentFire and currentFire.Enabled
	end,

	function(v)
        if currentFire then currentFire.Enabled = v end
	end
)

addNumber(
	"Size",

	function()
		return if currentFire then currentFire.Size else nil
	end,

	function(v)
        if currentFire then currentFire.Size = v end
	end,

	0.25,
	0,
	30,
	"%.2f"
)

addNumber(
	"Heat",

	function()
		return if currentFire then currentFire.Heat else nil
	end,

	function(v)
        if currentFire then currentFire.Heat = v end
	end,

	0.5,
	-25,
	25,
	"%.2f"
)

addNumber(
	"Time Scale",

	function()
		return if currentFire then currentFire.TimeScale else nil
	end,

	function(v)
        if currentFire then currentFire.TimeScale = v end
	end,

	0.05,
	0,
	1,
	"%.2f"
)

-- ============================================================
-- FIRE COLOR
-- ============================================================

addSection("FIRE COLOR")

addColorChannel(
	"Primary R",
	function() return currentFire end,
	"Color",
	"R"
)

addColorChannel(
	"Primary G",
	function() return currentFire end,
	"Color",
	"G"
)

addColorChannel(
	"Primary B",
	function() return currentFire end,
	"Color",
	"B"
)

addColorChannel(
	"Secondary R",
	function() return currentFire end,
	"SecondaryColor",
	"R"
)

addColorChannel(
	"Secondary G",
	function() return currentFire end,
	"SecondaryColor",
	"G"
)

addColorChannel(
	"Secondary B",
	function() return currentFire end,
	"SecondaryColor",
	"B"
)

-- ============================================================
-- LIGHT
-- ============================================================

addSection("POINT LIGHT")
addExplicitCreate("Create PointLight on selected Bone", createLight)

addToggle(
	"Enabled",

	function()
		return currentLight and currentLight.Enabled
	end,

	function(v)
        if currentLight then currentLight.Enabled = v end
	end
)

addToggle(
	"Shadows",

	function()
		return currentLight and currentLight.Shadows
	end,

	function(v)
        if currentLight then currentLight.Shadows = v end
	end
)

addNumber(
	"Brightness",

	function()
		return if currentLight then currentLight.Brightness else nil
	end,

	function(v)
        if currentLight then currentLight.Brightness = v end
	end,

	0.1,
	0,
	20,
	"%.2f"
)

addNumber(
	"Range",

	function()
		return if currentLight then currentLight.Range else nil
	end,

	function(v)
        if currentLight then currentLight.Range = v end
	end,

	1,
	0,
	60,
	"%.1f"
)

-- ============================================================
-- LIGHT COLOR
-- ============================================================

addSection("LIGHT COLOR")

addColorChannel(
	"Light R",
	function() return currentLight end,
	"Color",
	"R"
)

addColorChannel(
	"Light G",
	function() return currentLight end,
	"Color",
	"G"
)

addColorChannel(
	"Light B",
	function() return currentLight end,
	"Color",
	"B"
)

-- ============================================================
-- FIREFLY · LIGHT OF HEART (existing Game1OrbEffect renderer)
-- ============================================================

addSection("FIREFLY · LIGHT OF HEART")
addExplicitCreate("Create / register Firefly on selected Bone", createFirefly)
addToggle("Live Preview · Studio Edit",
    function() return previewEnabled end,
    function(enabled)
        previewEnabled = enabled
        if not enabled then discardPreview() else updatePreview(0) end
    end)
previewHint = Instance.new("TextLabel")
previewHint.Size = UDim2.new(1, -4, 0, 24)
previewHint.BackgroundTransparency = 1
previewHint.TextColor3 = MUTED
previewHint.Font = Enum.Font.Gotham
previewHint.TextSize = 11
previewHint.TextXAlignment = Enum.TextXAlignment.Left
previewHint.Text = "Select a Bone with Firefly to preview in Edit"
previewHint.Parent = scroll

addToggle("Firefly enabled",
    function() return currentOrb and currentOrb:GetAttribute("Enabled") end,
    function(value) if currentOrb then currentOrb:SetAttribute("Enabled", value) end end)
addToggle("Firefly shadows",
    function() return currentOrb and currentOrb:GetAttribute("Shadows") end,
    function(value) if currentOrb then currentOrb:SetAttribute("Shadows", value) end end)

local function fireflyNumber(name, key, step, minimum, maximum, format)
    addNumber(name,
        function() return currentOrb and currentOrb:GetAttribute(key) end,
        function(value) if currentOrb then currentOrb:SetAttribute(key, value) end end,
        step, minimum, maximum, format)
end
fireflyNumber("Orb radius", "Radius", 0.05, 0.06, 1.5, "%.2f")
fireflyNumber("Light brightness", "Brightness", 0.1, 0, 8, "%.2f")
fireflyNumber("Light range", "Range", 1, 0, 60, "%.1f")
fireflyNumber("Levitation height", "Lift", 0.1, -3, 6, "%.2f")
fireflyNumber("Levitation amplitude", "BobAmplitude", 0.05, 0, 2, "%.2f")
fireflyNumber("Levitation frequency", "BobFrequency", 0.05, 0, 3, "%.2f")
fireflyNumber("Side drift", "Drift", 0.05, 0, 2, "%.2f")
fireflyNumber("Random roam radius", "RoamRadius", 0.1, 0, 10, "%.2f")
fireflyNumber("Random roam speed", "RoamSpeed", 0.05, 0.05, 3, "%.2f")
for _, channel in ipairs({"R", "G", "B"}) do
    addNumber("Firefly color " .. channel,
        function()
            if not currentOrb then return nil end
            local color = currentOrb:GetAttribute("Color")
            if typeof(color) ~= "Color3" then return nil end
            return math.round(color[channel] * 255)
        end,
        function(value)
            if not currentOrb then return end
            local color = currentOrb:GetAttribute("Color")
            if typeof(color) ~= "Color3" then return end
            local r, g, b = math.round(color.R * 255), math.round(color.G * 255), math.round(color.B * 255)
            local v = math.round(value)
            if channel == "R" then r = v elseif channel == "G" then g = v else b = v end
            currentOrb:SetAttribute("Color", Color3.fromRGB(r, g, b))
        end, 10, 0, 255, "%d")
end

-- ============================================================
-- WORLD TIME
-- ============================================================

addSection("WORLD / TIME OF DAY")

local timeRow = Instance.new("Frame")
timeRow.Size = UDim2.new(1, -4, 0, 76)
timeRow.BackgroundColor3 = ROW
timeRow.BorderSizePixel = 0
timeRow.Parent = scroll
rounded(timeRow)

local timeName = Instance.new("TextLabel")
timeName.Position = UDim2.fromOffset(8, 4)
timeName.Size = UDim2.new(0.5, 0, 0, 24)
timeName.BackgroundTransparency = 1
timeName.Text = "Time of Day"
timeName.TextColor3 = TEXT
timeName.Font = Enum.Font.Gotham
timeName.TextSize = 12
timeName.TextXAlignment = Enum.TextXAlignment.Left
timeName.Parent = timeRow

local timeValue = Instance.new("TextLabel")
timeValue.AnchorPoint = Vector2.new(1, 0)
timeValue.Position = UDim2.new(1, -8, 0, 4)
timeValue.Size = UDim2.fromOffset(90, 24)
timeValue.BackgroundColor3 = Color3.fromRGB(25, 25, 29)
timeValue.BorderSizePixel = 0
timeValue.TextColor3 = VALUE
timeValue.Font = Enum.Font.Code
timeValue.TextSize = 12
timeValue.Parent = timeRow
rounded(timeValue, 4)

local slider = Instance.new("Frame")
slider.Position = UDim2.fromOffset(12, 47)
slider.Size = UDim2.new(1, -24, 0, 8)
slider.BackgroundColor3 = Color3.fromRGB(69, 69, 77)
slider.BorderSizePixel = 0
slider.Parent = timeRow
rounded(slider, 8)

local fill = Instance.new("Frame")
fill.Size = UDim2.fromScale(0, 1)
fill.BackgroundColor3 = ACCENT
fill.BorderSizePixel = 0
fill.Parent = slider
rounded(fill, 8)

local knob = Instance.new("Frame")
knob.AnchorPoint = Vector2.new(0.5, 0.5)
knob.Position = UDim2.fromScale(0, 0.5)
knob.Size = UDim2.fromOffset(16, 16)
knob.BackgroundColor3 = Color3.fromRGB(245, 245, 245)
knob.BorderSizePixel = 0
knob.Parent = slider
rounded(knob, 8)

local function clockText(clock)

	clock %= 24

	local h = math.floor(clock)

	local m =
		math.floor(
			(clock - h) * 60 + 0.5
		)

	if m >= 60 then
		h = (h + 1) % 24
		m = 0
	end

	return string.format("%02d:%02d", h, m)
end

local function refreshTime()

	local clock =
		Lighting.ClockTime % 24

	local alpha =
		clock / 24

	fill.Size =
		UDim2.fromScale(alpha, 1)

	knob.Position =
		UDim2.fromScale(alpha, 0.5)

	timeValue.Text =
		clockText(clock)
end

local timeDragging = false

local function setTime(mouseX)

	local width =
		slider.AbsoluteSize.X

	if width <= 0 then
		return
	end

	local alpha =
		math.clamp(
			(
				mouseX
				- slider.AbsolutePosition.X
			) / width,
			0,
			1
		)

	local clock =
		alpha * 24

	local shift =
		UserInputService:IsKeyDown(
			Enum.KeyCode.LeftShift
		)
		or UserInputService:IsKeyDown(
			Enum.KeyCode.RightShift
		)

	local alt =
		UserInputService:IsKeyDown(
			Enum.KeyCode.LeftAlt
		)
		or UserInputService:IsKeyDown(
			Enum.KeyCode.RightAlt
		)

	if shift then

		clock =
			math.round(clock)

	elseif alt then

		local fiveMinutes =
			5 / 60

		clock =
			math.round(
				clock / fiveMinutes
			)
			* fiveMinutes
	end

	if clock >= 24 then
		clock = 23.999
	end

	Lighting.ClockTime = clock

	refreshTime()
end

local function beginTimeDrag(input)

	if input.UserInputType
		~= Enum.UserInputType.MouseButton1
	then
		return
	end

	timeDragging = true
	setTime(input.Position.X)
end

slider.InputBegan:Connect(beginTimeDrag)
knob.InputBegan:Connect(beginTimeDrag)

UserInputService.InputChanged:Connect(function(input)

	if not timeDragging then
		return
	end

	if input.UserInputType
		== Enum.UserInputType.MouseMovement
	then
		setTime(input.Position.X)
	end
end)

UserInputService.InputEnded:Connect(function(input)

	if input.UserInputType
		== Enum.UserInputType.MouseButton1
	then
		timeDragging = false
	end
end)

Lighting:GetPropertyChangedSignal(
	"ClockTime"
):Connect(refreshTime)

refreshTime()

-- ============================================================
-- TOOLBAR / WINDOW
-- ============================================================

toolbarButton.Click:Connect(function()

	widget.Enabled =
		not widget.Enabled

	toolbarButton:SetActive(
		widget.Enabled
	)

	if not widget.Enabled then discardPreview() end

	if widget.Enabled then

        -- Inspect the selected Bone on opening without altering its effects.
		local selected = Selection:Get()

		if #selected == 1
			and selected[1]:IsA("Bone")

		then
			bindSelected()
		end
	end
end)

widget:BindToClose(function()
	toolbarButton:SetActive(false)
    discardPreview()
end)

plugin.Unloading:Connect(function()
    previewConnection:Disconnect()
    discardPreview()
end)

print("[Game1] Fire Bone Tuner plugin loaded")