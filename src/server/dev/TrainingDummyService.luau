local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local CombatRoot = script.Parent.Parent:WaitForChild("combat")
local DeathLifecycleService = require(CombatRoot:WaitForChild("DeathLifecycleService"))
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))

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
    if not RunService:IsStudio() then
        return
    end

    local model = Workspace:FindFirstChild("game1TrainingDummy")
    if not model or not model:IsA("Model") then
        warn("[game1][DUMMY] game1TrainingDummy model is required in Studio")
        return
    end

    local root = model:FindFirstChild("RootCollider") or model.PrimaryPart
    if not root or not root:IsA("BasePart") then
        warn("[game1][DUMMY] training dummy has no RootCollider/PrimaryPart")
        return
    end

    model:SetAttribute("Damageable", model:GetAttribute("Damageable") ~= false)
    model:SetAttribute("LifeState", tostring(model:GetAttribute("LifeState") or "Alive"))
    if not model:FindFirstChild("StatusGui") then
        createStatusGui(root, model)
    end

    -- The training dummy uses the same precomputed combat hitboxes as
    -- characters and monsters; RootCollider is never a melee damage volume.
    local visual = model:FindFirstChild("Visual")
        or model:FindFirstChild("ImportedRig")
        or model
    if visual:IsA("Model") then
        local binding = EntityHitboxService.Attach(model, visual)
        print(("[game1][DUMMY] combat hitboxes attached · boxes=%d · head=%s")
            :format(binding.count, tostring(binding.hasHead)))
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
                model:SetAttribute("HP", tonumber(model:GetAttribute("MaxHP")) or 100)
                model:SetAttribute("Damageable", true)
                model:SetAttribute("LifeState", "Alive")
                print("[game1][DUMMY] reset · combat hitboxes preserved")
            end
        end)
    end)
end

return Service
