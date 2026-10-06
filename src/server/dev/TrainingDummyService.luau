local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local DeathLifecycleService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("DeathLifecycleService"))

local Service = {}

local function createStatusGui(root: BasePart, model: Model)
    local billboard = Instance.new("BillboardGui")
    billboard.Name = "StatusGui"
    billboard.Adornee = root
    billboard.AlwaysOnTop = true
    billboard.Size = UDim2.fromOffset(240, 70)
    billboard.StudsOffset = Vector3.new(0, 4.25, 0)
    billboard.Parent = model

    local label = Instance.new("TextLabel")
    label.Name = "StatusText"
    label.Size = UDim2.fromScale(1, 1)
    label.BackgroundTransparency = 0.2
    label.TextScaled = true
    label.TextWrapped = true
    label.Parent = billboard

    local function render()
        local hp = tonumber(model:GetAttribute("HP")) or 0
        local maxHP = tonumber(model:GetAttribute("MaxHP")) or 0
        local defense = tonumber(model:GetAttribute("Defense")) or 0
        label.Text = ("TRAINING DUMMY\nHP %d/%d   DEF %d"):format(hp, maxHP, defense)
    end

    model:GetAttributeChangedSignal("HP"):Connect(render)
    model:GetAttributeChangedSignal("MaxHP"):Connect(render)
    model:GetAttributeChangedSignal("Defense"):Connect(render)
    render()
end

function Service.Start()
    if not RunService:IsStudio() or Workspace:FindFirstChild("game1TrainingDummy") then
        return
    end

    local spawn = Workspace:FindFirstChildWhichIsA("SpawnLocation", true)

    local model = Instance.new("Model")
    model.Name = "game1TrainingDummy"
    model:SetAttribute("Damageable", true)
    model:SetAttribute("Level", 1)
    model:SetAttribute("MaxHP", 100)
    model:SetAttribute("HP", 100)
    model:SetAttribute("Damage", 0)
    model:SetAttribute("Defense", 0)
    model:SetAttribute("LifeState", "Alive")

    local root = Instance.new("Part")
    root.Name = "RootCollider"
    root.Size = Vector3.new(3, 5, 3)
    root.Anchored = true
    root.Position = (spawn and spawn.Position or Vector3.zero) + Vector3.new(0, 2.5, -6)
    root.Parent = model

    model.PrimaryPart = root
    model.Parent = Workspace

    createStatusGui(root, model)

    if RunService:IsStudio() then
        print("[game1][DUMMY] spawned · HP=100/100 DEF=0 · attack with LMB inside melee range")
    end

    local spawnCFrame = root.CFrame
    model:GetAttributeChangedSignal("LifeState"):Connect(function()
        if tostring(model:GetAttribute("LifeState") or "") ~= "Dying" then
            return
        end
        print("[game1][DUMMY] dying · shared 5s DeathIdle presentation")
        DeathLifecycleService.BeginDeathIdle(model, root, model, function()
            if model.Parent then
                root.CFrame = spawnCFrame
                model:SetAttribute("HP", 100)
                model:SetAttribute("Damageable", true)
                model:SetAttribute("LifeState", "Alive")
                print("[game1][DUMMY] reset · HP=100/100")
            end
        end)
    end)
end

return Service
