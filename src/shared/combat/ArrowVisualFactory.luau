-- Shared cosmetic arrow factory: server publishes the active template once.
-- Client clones and animates locally; meshes never decide damage.
local RunService = game:GetService("RunService")
local ServerStorage = if RunService:IsServer() then game:GetService("ServerStorage") else nil
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Registry = require(Shared:WaitForChild("weapon"):WaitForChild("ArrowRegistry"))
local Policy = require(Shared:WaitForChild("combat"):WaitForChild("BowProjectileConfig"))

local Factory = {}
local ROTATIONS = table.freeze({
    ["-Z"] = CFrame.identity,
    ["+Z"] = CFrame.Angles(0, math.pi, 0),
    ["+X"] = CFrame.Angles(0, math.pi/2, 0),
    ["-X"] = CFrame.Angles(0, -math.pi/2, 0),
    ["+Y"] = CFrame.Angles(-math.pi/2, 0, 0),
    ["-Y"] = CFrame.Angles(math.pi/2, 0, 0),
})

function Factory.ActiveDefinition(): (string, any?, number)
    local slug = tostring(Registry.activeArrowSlug or "")
    local row = Registry.arrows and Registry.arrows[slug]
    if type(row) ~= "table" or row.status ~= "PUBLISHED" then
        return "", nil, Policy.DefaultSpeed
    end
    return slug, row, math.clamp(tonumber(row.speed) or Policy.DefaultSpeed, 20, 500)
end

local function templateFor(row: any): Model?
    if type(row) ~= "table" then return nil end
    local path = tostring(row.serverStoragePath or "")
    if path:sub(1, 14) ~= "ServerStorage." then return nil end
    if not ServerStorage then return nil end
    local cursor: Instance = ServerStorage
    for segment in path:sub(15):gmatch("[^%.]+") do
        local child = cursor:FindFirstChild(segment)
        if not child then return nil end
        cursor = child
    end
    return if cursor:IsA("Model") and cursor:FindFirstChildWhichIsA("BasePart", true) then cursor else nil
end

-- Only one active published arrow needs replication. Do not publish any user
-- asset or Model ID: this is an in-memory visual clone for current clients.
function Factory.PublishActiveTemplate()
    if not RunService:IsServer() then return end
    local slug, row = Factory.ActiveDefinition()
    local root = ReplicatedStorage:FindFirstChild("Game1ArrowTemplates")
    if not root then
        root = Instance.new("Folder")
        root.Name = "Game1ArrowTemplates"
        root.Parent = ReplicatedStorage
    end
    root:ClearAllChildren()
    local template = templateFor(row)
    if not template then return end
    local clone = template:Clone()
    clone.Name = slug
    for _, node in ipairs(clone:GetDescendants()) do
        if node:IsA("LuaSourceContainer") or node:IsA("Humanoid") or node:IsA("AnimationController") then
            node:Destroy()
        elseif node:IsA("BasePart") then
            node.Anchored = true
            node.CanCollide = false
            node.CanQuery = false
            node.CanTouch = false
            node.Massless = true
        end
    end
    clone.Parent = root
end

local function procedural(): Model
    local visual = Instance.new("Model")
    visual.Name = "Game1BowArrow"
    local shaft = Instance.new("Part")
    shaft.Name = "ArrowShaft"
    shaft.Size = Vector3.new(0.095, 0.095, 2)
    shaft.Material = Enum.Material.Wood
    shaft.Color = Color3.fromRGB(130, 92, 50)
    shaft.Anchored = true
    shaft.Parent = visual
    local tip = Instance.new("Part")
    tip.Name = "ArrowTip"
    tip.Shape = Enum.PartType.Ball
    tip.Size = Vector3.new(0.18, 0.18, 0.3)
    tip.Material = Enum.Material.Metal
    tip.Color = Color3.fromRGB(178, 184, 186)
    tip.CFrame = CFrame.new(0, 0, -1)
    tip.Anchored = true
    tip.Parent = visual
    visual.PrimaryPart = shaft
    return visual
end

function Factory.Create(row: any, slug: string, frame: CFrame, parent: Instance): (Model, CFrame)
    local repository = ReplicatedStorage:FindFirstChild("Game1ArrowTemplates")
    local template = if repository then repository:FindFirstChild(slug) else nil
    local visual = if template and template:IsA("Model") then template:Clone() else procedural()
    visual.Name = "Game1BowArrow"
    for _, child in ipairs(visual:GetDescendants()) do
        if child:IsA("LuaSourceContainer") or child:IsA("Humanoid") or child:IsA("AnimationController") then
            child:Destroy()
        elseif child:IsA("BasePart") then
            child.Anchored = true
            child.CanCollide = false
            child.CanTouch = false
            child.CanQuery = false
            child.CastShadow = false
            child.Massless = true
        end
    end
    local correction = ROTATIONS[if row then row.forwardAxis else "-Z"] or CFrame.identity
    visual:SetAttribute("ArrowSlug", slug)
    -- Place before parenting: no single-frame flash at the stored template origin.
    visual:PivotTo(frame * correction)
    visual.Parent = parent
    return visual, correction
end

-- Projection of the visible arrow's actual frontmost geometry along flight.
-- Handles an FBX-authored pivot, arbitrary mesh axes and the procedural arrow.
function Factory.ContactFrame(visual: Model, contact: Vector3, travelDirection: Vector3,
    penetrationStuds: number, hitPart: Instance?): CFrame
    local direction = travelDirection.Unit
    local pivot = visual:GetPivot().Position
    local tip = -math.huge
    for _, item in ipairs(visual:GetDescendants()) do
        if item:IsA("BasePart") and item.Transparency < 1 then
            local axisX, axisY, axisZ = item.CFrame.RightVector, item.CFrame.UpVector, item.CFrame.LookVector
            local extents = item.Size * 0.5
            local extent = math.abs(axisX:Dot(direction)) * extents.X
                + math.abs(axisY:Dot(direction)) * extents.Y
                + math.abs(axisZ:Dot(direction)) * extents.Z
            tip = math.max(tip, (item.Position - pivot):Dot(direction) + extent)
        end
    end
    if tip == -math.huge then tip = 0 end
    local depth = math.clamp(tonumber(penetrationStuds) or 0.12, 0, 3)
    if hitPart and hitPart:IsA("BasePart") then
        -- An authored deep penetration must not bury the arrow THROUGH a thin
        -- lantern casing; base the safe cap on its oriented projected width.
        local width = math.abs(hitPart.CFrame.RightVector:Dot(direction)) * hitPart.Size.X
            + math.abs(hitPart.CFrame.UpVector:Dot(direction)) * hitPart.Size.Y
            + math.abs(hitPart.CFrame.LookVector:Dot(direction)) * hitPart.Size.Z
        depth = math.min(depth, math.max(0.025, width * 0.35))
    end
    local target = contact - direction * (tip - depth)
    local up = if math.abs(direction:Dot(Vector3.yAxis)) > 0.98 then Vector3.zAxis else Vector3.yAxis
    return CFrame.lookAt(target, target + direction, up)
end

function Factory.Place(visual: Model, frame: CFrame, correction: CFrame)
    visual:PivotTo(frame * correction)
end

return table.freeze(Factory)
