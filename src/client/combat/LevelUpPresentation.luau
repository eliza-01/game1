--!strict
-- Reward feedback only; no gameplay mutations or input interception.
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local Debris = game:GetService("Debris")
local player = Players.LocalPlayer
local Presentation = {}
local active: ScreenGui? = nil
local gold = Color3.fromRGB(255, 215, 100)

local function stars(character: Model)
    local root = character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then return end
    for i = 1, 5 do
        local angle = (i-1)*math.pi*2/5
        local attachment = Instance.new("Attachment")
        attachment.Name = "LevelUpStars"
        attachment.Position = Vector3.new(math.cos(angle)*1.6, 5, math.sin(angle)*1.6)
        attachment.Parent = root
        local emitter = Instance.new("ParticleEmitter")
        emitter.Texture = "rbxasset://textures/particles/sparkles_main.dds"
        emitter.Color = ColorSequence.new(gold)
        emitter.Rate = 0
        emitter.Lifetime = NumberRange.new(.9, 1.45)
        emitter.Speed = NumberRange.new(3.5, 6)
        emitter.Acceleration = Vector3.new(0, -3, 0)
        emitter.EmissionDirection = Enum.NormalId.Bottom
        emitter.SpreadAngle = Vector2.new(12, 12)
        emitter.RotSpeed = NumberRange.new(-65, 65)
        emitter.LightEmission = .85
        emitter.LockedToPart = true
        emitter.Size = NumberSequence.new({NumberSequenceKeypoint.new(0,.22), NumberSequenceKeypoint.new(.25,.45), NumberSequenceKeypoint.new(1,0)})
        emitter.Transparency = NumberSequence.new({NumberSequenceKeypoint.new(0,.05), NumberSequenceKeypoint.new(.6,.15), NumberSequenceKeypoint.new(1,1)})
        emitter.Parent = attachment
        emitter:Emit(9)
        Debris:AddItem(attachment, 1.6)
    end
end

local function label(parent: Frame, name: string, y: number, height: number, size: number, text: string, color: Color3): TextLabel
    local item = Instance.new("TextLabel")
    item.Name = name; item.BackgroundTransparency = 1; item.Active = false
    item.Size = UDim2.new(1, 0, 0, height); item.Position = UDim2.fromOffset(0, y)
    item.Font = Enum.Font.GothamBold; item.TextSize = size; item.Text = text
    item.TextColor3 = color; item.TextStrokeTransparency = .25
    item.TextTransparency = 1; item.Parent = parent
    TweenService:Create(item, TweenInfo.new(.2), {TextTransparency = 0}):Play()
    return item
end

local function signed(value: any): string
    return string.format("%+g", math.round((tonumber(value) or 0)*100)/100)
end

function Presentation.Show(payload: any)
    local character = player.Character
    local level = tonumber(payload.level)
    if not character or payload.target ~= character or not level then return end
    stars(character)
    if active then active:Destroy() end
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1LevelUp"; gui.IgnoreGuiInset = true; gui.ResetOnSpawn = true; gui.DisplayOrder = 24
    gui.Parent = player:WaitForChild("PlayerGui")
    active = gui
    local panel = Instance.new("Frame")
    panel.Name = "LevelUpNotice"; panel.BackgroundTransparency = 1; panel.Active = false
    panel:SetAttribute("WorldInputPassthrough", true)
    panel.AnchorPoint = Vector2.new(.5,.5); panel.Position = UDim2.fromScale(.5,.5)
    panel.Size = UDim2.new(.9,0,0,100); panel.Parent = gui
    local title = label(panel,"Level",0,54,36,string.format("Level %d",level),gold)
    local stats = label(panel,"Gains",54,32,21,signed(payload.hpGain).." HP    "..signed(payload.attackGain).." ATK",Color3.new(1,1,1))
    task.delay(1.65,function()
        if not gui.Parent then return end
        for _, item in ipairs({title,stats}) do
            TweenService:Create(item,TweenInfo.new(.35),{TextTransparency=1,TextStrokeTransparency=1}):Play()
        end
        task.delay(.4,function()
            if active == gui then active = nil end
            gui:Destroy()
        end)
    end)
end
return table.freeze(Presentation)
