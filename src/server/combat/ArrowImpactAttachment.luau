-- Cosmetic stuck arrows: native weld on moving rigid props; short-lived bone-local
-- follow on animated skinned rigs. Damage and projectile collision live elsewhere.
-- Same principle as the legacy Lineage animated-arrow attachment, with ONE
-- bounded Heartbeat for currently attached arrows (not one event per arrow).
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local ArrowImpactAttachment = {}
local animated = {}
local connection: RBXScriptConnection? = nil
local elapsed = 0
local STEP = 1 / 30

local function update(dt: number)
    elapsed += dt
    if elapsed < STEP then return end
    elapsed %= STEP
    for visual, binding in pairs(animated) do
        if not visual.Parent or not binding.bone.Parent or not binding.bone:IsDescendantOf(Workspace) then
            animated[visual] = nil
        else
            visual:PivotTo(binding.bone.TransformedWorldCFrame * binding.localFrame)
        end
    end
    if next(animated) == nil and connection then
        connection:Disconnect()
        connection = nil
    end
end

local function animatedBone(entity: Model?, name: string?, at: Vector3): Bone?
    if not entity or not entity.Parent then return nil end
    local visual = entity:FindFirstChild("Visual") or entity:FindFirstChild("ImportedRig") or entity
    local nearest: Bone? = nil
    local distance = math.huge
    for _, node in ipairs(visual:GetDescendants()) do
        if node:IsA("Bone") then
            if name and name ~= "" and node.Name == name then return node end
            local d = (node.TransformedWorldCFrame.Position - at).Magnitude
            if d < distance then distance = d; nearest = node end
        end
    end
    return nearest
end

local function partOfModel(model: Model?): BasePart?
    if not model or not model.Parent then return nil end
    local root = model:FindFirstChild("RootCollider") or model:FindFirstChild("HumanoidRootPart")
    if root and root:IsA("BasePart") then return root end
    if model.PrimaryPart then return model.PrimaryPart end
    return model:FindFirstChildWhichIsA("BasePart", true)
end

local function carrier(hitInstance: Instance?, entity: Model?): BasePart?
    if entity then return partOfModel(entity) end
    return if hitInstance and hitInstance:IsA("BasePart") then hitInstance else nil
end

local function managedModel(part: BasePart): Model?
    local cursor: Instance? = part.Parent
    while cursor and cursor ~= Workspace do
        if cursor:IsA("Model") then return cursor end
        cursor = cursor.Parent
    end
    return nil
end

function ArrowImpactAttachment.Attach(visual: Model, hitInstance: Instance?, entity: Model?, boneName: string?): boolean
    local hitPart = carrier(hitInstance, entity)
    if not hitPart or not hitPart:IsDescendantOf(Workspace) then return false end
    local bone = animatedBone(entity, boneName, visual:GetPivot().Position)
    local parent = (entity and entity.Parent and entity) or managedModel(hitPart) or hitPart
    visual.Parent = parent
    if bone then
        -- WeldConstraint to RootCollider is WRONG for a skinned Death animation.
        -- Keep arrow offset in animated Bone space until Debris removes it.
        for _, part in ipairs(visual:GetDescendants()) do
            if part:IsA("BasePart") then
                part.Anchored = true
                part.Massless = true
                part.CanCollide = false
                part.CanTouch = false
                part.CanQuery = false
            end
        end
        animated[visual] = {
            bone = bone,
            localFrame = bone.TransformedWorldCFrame:ToObjectSpace(visual:GetPivot()),
        }
        if not connection then connection = RunService.Heartbeat:Connect(update) end
        return true
    end
    -- Rigid moving prop: weld just one arrow root and weld internal arrow parts
    -- to that root (one connected assembly, no redundant root welds).
    local arrowRoot = visual.PrimaryPart or visual:FindFirstChildWhichIsA("BasePart", true)
    if not arrowRoot then return false end
    for _, part in ipairs(visual:GetDescendants()) do
        if part:IsA("BasePart") then
            part.Anchored = false
            part.Massless = true
            part.CanCollide = false
            part.CanTouch = false
            part.CanQuery = false
            if part ~= arrowRoot then
                local internal = Instance.new("WeldConstraint")
                internal.Name = "ArrowInternalWeld"
                internal.Part0 = arrowRoot
                internal.Part1 = part
                internal.Parent = part
            end
        end
    end
    local weld = Instance.new("WeldConstraint")
    weld.Name = "ArrowImpactWeld"
    weld.Part0 = hitPart
    weld.Part1 = arrowRoot
    weld.Parent = arrowRoot
    return true
end

return table.freeze(ArrowImpactAttachment)
