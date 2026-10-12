-- Studio-only representation of the published NPC while authoring a spawn point.
-- Runtime entities are created exclusively by NpcRigFactory/NpcSpawnerService.
local NpcSpawnPreview = {}

local function publishedTemplate(serverStorage: ServerStorage, slug: string): Model?
    local npcs = serverStorage:FindFirstChild("npcs")
    local actor = npcs and npcs:FindFirstChild(slug)
    local container = actor and actor:FindFirstChild("model")
    local source = container and container:FindFirstChild(slug)
    if source and source:IsA("Model") and source:GetAttribute("Game1NpcRig") == true then
        return source
    end
    return nil
end

local function geometryBounds(visual: Model): (CFrame, Vector3)
    -- Same support-surface convention as NpcRigFactory.visibleBounds.
    local low = Vector3.new(math.huge, math.huge, math.huge)
    local high = Vector3.new(-math.huge, -math.huge, -math.huge)
    local found = false
    for _, part in ipairs(visual:GetDescendants()) do
        if part:IsA("BasePart") and part.Name ~= "RootPart" and part.Name ~= "RootCollider" then
            found = true
            local half = part.Size * 0.5
            for x = -1, 1, 2 do
                for y = -1, 1, 2 do
                    for z = -1, 1, 2 do
                        local point = part.CFrame:PointToWorldSpace(Vector3.new(half.X * x, half.Y * y, half.Z * z))
                        low = Vector3.new(math.min(low.X, point.X), math.min(low.Y, point.Y), math.min(low.Z, point.Z))
                        high = Vector3.new(math.max(high.X, point.X), math.max(high.Y, point.Y), math.max(high.Z, point.Z))
                    end
                end
            end
        end
    end
    if not found then
        return visual:GetBoundingBox()
    end
    return CFrame.new((low + high) * 0.5), high - low
end

function NpcSpawnPreview.Attach(serverStorage: ServerStorage, marker: Model, slug: string): Model
    local template = publishedTemplate(serverStorage, slug)
    if not template then
        error("NPC preview template is missing from ServerStorage.npcs." .. slug .. ".model." .. slug .. "; synchronize the published rig first")
    end
    local ghost = template:Clone()
    if not ghost then
        error("NPC template cannot be cloned: " .. slug)
    end
    ghost.Name = "ActorPreview"
    local initialRotation = ghost:GetPivot().Rotation
    for _, instance in ipairs(ghost:GetDescendants()) do
        if instance:IsA("BasePart") then
            instance.Anchored = true
            instance.CanCollide = false
            instance.CanTouch = false
            instance.CanQuery = false
            instance.CastShadow = false
            if instance.Name == "RootPart" or instance.Name == "RootCollider" or instance.Name == "NavigationRoot" then
                instance.Transparency = 1
            else
                instance.Transparency = math.max(instance.Transparency, 0.28)
            end
        elseif instance:IsA("Script") or instance:IsA("LocalScript") or instance:IsA("ModuleScript") then
            instance:Destroy()
        elseif instance:IsA("Humanoid") then
            instance:Destroy()
        end
    end
    -- Normalize at yaw=0 before measuring the lowest visible vertex.
    ghost:PivotTo(initialRotation)
    local visual = ghost:FindFirstChild("ImportedRig")
    if not visual or not visual:IsA("Model") then
        visual = ghost
    end
    local bounds, size = geometryBounds(visual :: Model)
    local offset = size.Y * 0.5 - bounds.Position.Y
    ghost:SetAttribute("PreviewBaseRotation", initialRotation)
    ghost:SetAttribute("PreviewGroundOffset", offset)
    ghost:SetAttribute("Game1NpcPlacementVisual", true)
    ghost.Parent = marker
    return ghost
end

function NpcSpawnPreview.Move(marker: Model, position: Vector3, yawDegrees: number)
    local ghost = marker:FindFirstChild("ActorPreview")
    if not ghost or not ghost:IsA("Model") then
        return
    end
    local rotation = ghost:GetAttribute("PreviewBaseRotation")
    local offset = ghost:GetAttribute("PreviewGroundOffset")
    if typeof(rotation) ~= "CFrame" or type(offset) ~= "number" then
        return
    end
    ghost:PivotTo(CFrame.new(position + Vector3.new(0, offset, 0))
        * CFrame.Angles(0, math.rad(yawDegrees), 0) * rotation)
end

return table.freeze(NpcSpawnPreview)
