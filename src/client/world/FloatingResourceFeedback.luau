--!strict
-- Reusable client-only presentation for server-confirmed resource deltas.
-- Both +receipts and -spends use the same head-anchored, content-sized UI.
-- No inventory mutation, world parts, or gameplay authority live here.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TextService = game:GetService("TextService")
local TweenService = game:GetService("TweenService")

local SpatialRoot = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local UiSettings = require(script.Parent:WaitForChild("UiPresentationSettings"))
local Language = require(script.Parent.Parent:WaitForChild("localization"):WaitForChild("LanguageState"))

local player = Players.LocalPlayer
local Feedback = {}
local ICONS = table.freeze({
    wood = "🪵",
    carrot = "🥕",
    onion = "🧅",
    potato = "🥔",
    meal = "🍲",
})
local MAX_TEXT_WIDTH = 420

local function anchorForPlayer(): (Instance?, number)
    local character = player.Character
    if not character then return nil, 0 end
    -- Custom skinned rigs have a real animated head Bone, not a Roblox Head
    -- part. Bone extends Attachment, so BillboardGui can follow its HEAD.
    if SpatialRoot.IsCustom(player) then
        -- Prefer the canonical carrier rather than an unbound Bone of the
        -- same name in a separate accessory/skinned visual MeshPart.
        local carrier = character:FindFirstChild("rig_carrier", true)
        local head = if carrier then carrier:FindFirstChild("head", true) else nil
        if head and head:IsA("Bone") then return head, 0.9 end
        head = character:FindFirstChild("head", true)
        if head and head:IsA("Bone") then return head, 0.9 end
    end
    local head = character:FindFirstChild("Head", true)
    if head and head:IsA("BasePart") then
        return head, head.Size.Y * 0.5 + 0.75
    end
    local root = SpatialRoot.Get(player)
    if root then return root, math.max(3.2, root.Size.Y * 0.5 + 2.1) end
    return nil, 0
end

local function rounded(parent: GuiObject, radiusPx: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, radiusPx)
    corner.Parent = parent
end

local function showLine(anchor: Instance, headOffset: number, text: string, positive: boolean,
    index: number, config: {[string]: any}, animated: boolean): BillboardGui
    local fontPx = tonumber(config.fontPx) or 18
    local padding = tonumber(config.paddingPx) or 5
    local maxTextWidth = MAX_TEXT_WIDTH - padding * 2
    local measured = TextService:GetTextSize(text, fontPx, Enum.Font.GothamBold,
        Vector2.new(maxTextWidth, 200))
    local width = measured.X + padding * 2
    local height = measured.Y + padding * 2

    local billboard = Instance.new("BillboardGui")
    billboard.Name = "Game1ResourceFloat"
    billboard:SetAttribute("WorldInputPassthrough", true)
    billboard.Active = false
    billboard.Adornee = anchor
    billboard.AlwaysOnTop = true
    billboard.LightInfluence = 0
    billboard.MaxDistance = 160
    -- The transparent BillboardGui canvas is not the notification background.
    -- The frame below is exactly the measured text plus configurable padding.
    billboard.Size = UDim2.fromOffset(MAX_TEXT_WIDTH + 20, math.max(90, height + config.risePx + 24))
    billboard.StudsOffsetWorldSpace = Vector3.new(0, headOffset, 0)
    billboard.Parent = player:WaitForChild("PlayerGui")

    local box = Instance.new("Frame")
    box.Name = "ContentBox"
    box.AnchorPoint = Vector2.new(0.5, 0.5)
    box.Position = UDim2.new(0.5, config.offsetXPx, 0.5,
        config.offsetYPx - (index - 1) * (height + 4))
    box.Size = UDim2.fromOffset(width, height)
    box.BackgroundColor3 = Color3.fromRGB(21, 29, 38)
    box.BackgroundTransparency = 0.12
    box.BorderSizePixel = 0
    box.Parent = billboard
    rounded(box, math.min(7, padding + 2))

    local label = Instance.new("TextLabel")
    label.Name = "ResourceText"
    label.BackgroundTransparency = 1
    label.Position = UDim2.fromOffset(padding, padding)
    label.Size = UDim2.fromOffset(measured.X, measured.Y)
    label.Font = Enum.Font.GothamBold
    label.TextSize = fontPx
    label.TextWrapped = true
    label.Text = text
    label.TextColor3 = if positive then Color3.fromRGB(132, 237, 181)
        else Color3.fromRGB(255, 191, 145)
    label.TextXAlignment = Enum.TextXAlignment.Center
    label.Parent = box

    if animated then
        local duration = tonumber(config.durationSeconds) or 0.9
        local rise = tonumber(config.risePx) or 34
        local tween = TweenInfo.new(duration, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
        TweenService:Create(box, tween, {
            Position = box.Position - UDim2.fromOffset(0, rise),
            BackgroundTransparency = 1,
        }):Play()
        TweenService:Create(label, tween, {TextTransparency = 1}):Play()
        task.delay(duration + 0.1, function() billboard:Destroy() end)
    end
    return billboard
end

function Feedback.Show(items: {any})
    if type(items) ~= "table" then return end
    local anchor, offset = anchorForPlayer()
    if not anchor then return end
    local cfg = UiSettings.Current().resource
    local index = 0
    for _, item in ipairs(items) do
        if type(item) ~= "table" then continue end
        local amount = tonumber(item.amount)
        if not amount or amount ~= amount or amount == math.huge or amount == -math.huge
            or amount == 0 then continue end
        local icon = ICONS[tostring(item.icon or "")] or "•"
        local count = math.max(1, math.floor(math.abs(amount) + 0.5))
        local text = string.format("%s  %s%d  %s", icon, if amount > 0 then "+" else "−",
            count, Language.FromSource(tostring(item.label or "")))
        index += 1
        showLine(anchor, offset, text, amount > 0, index, cfg, true)
        if index >= 8 then break end
    end
end

-- Studio-only caller owns the returned preview and destroys it on each change.
-- It is the exact same head anchor, text measurement and padding as gameplay.
function Feedback.Preview(config: {[string]: any}): BillboardGui?
    local anchor, offset = anchorForPlayer()
    if not anchor then return nil end
    local sample = showLine(anchor, offset, "🪵  −5  Дерево", false, 1, config, false)
    sample.Name = "Game1ResourcePreview"
    return sample
end

return table.freeze(Feedback)
