-- Local-only mobile target acquisition. No damage or server state is changed.
-- Monsters with no literal neck bone (including the current Gremlin) use
-- their authored upper-neck chain spine.003, then head if needed.
local Workspace = game:GetService("Workspace")
local Targeting = {}

local function anchor(model: Model): BasePart?
    local root = model:FindFirstChild("RootCollider") or model:FindFirstChild("HumanoidRootPart")
    return if root and root:IsA("BasePart") then root else nil
end

local function findBone(model: Model): Bone?
    local upperSpine: Bone? = nil
    local head: Bone? = nil
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("Bone") then
            local name = item.Name:lower()
            if name == "neck" then return item end
            if name == "spine.003" or name == "spine_03" then upperSpine = item end
            if name == "head" then head = item end
        end
    end
    return upperSpine or head
end

function Targeting.Point(model: Model, bone: Bone): Vector3?
    if not model.Parent or not bone:IsDescendantOf(model)
        or model:GetAttribute("LifeState") ~= "Alive" then return nil end
    return bone.TransformedWorldCFrame.Position
end

function Targeting.Acquire(character: Model, maxDistance: number): (Model?, Bone?)
    local playerRoot = anchor(character)
    local folder = Workspace:FindFirstChild("Monsters")
    local camera = Workspace.CurrentCamera
    if not playerRoot or not folder or not camera then return nil, nil end
    local best: Model? = nil
    local bestBone: Bone? = nil
    local bestSquared = maxDistance * maxDistance
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.RespectCanCollide = false
    for _, candidate in ipairs(folder:GetChildren()) do
        if candidate:IsA("Model") and candidate:GetAttribute("LifeState") == "Alive" then
            local root = anchor(candidate)
            if root then
                local squared = (root.Position - playerRoot.Position):Dot(root.Position - playerRoot.Position)
                if squared <= bestSquared then
                    local bone = findBone(candidate)
                    local point = bone and Targeting.Point(candidate, bone)
                    if bone and point then
                        -- Do not lock through walls. Target geometry is excluded
                        -- from the obstruction test, not the rest of the world.
                        params.FilterDescendantsInstances = {character, candidate}
                        local ray = point - camera.CFrame.Position
                        local blocked = Workspace:Raycast(camera.CFrame.Position, ray, params)
                        if not blocked then
                            best, bestBone, bestSquared = candidate, bone, squared
                        end
                    end
                end
            end
        end
    end
    return best, bestBone
end

return table.freeze(Targeting)
