-- Client-only visual arrows. Game1's authoritative Head/Body result was already
-- decided at Release; no per-frame raycasts, physics or hit remotes are used.
-- Bone-local sticking follows the proven RobloxLineage presentation principle.
local Debris = game:GetService("Debris")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Combat = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("combat")
local Factory = require(Combat:WaitForChild("ArrowVisualFactory"))
local Policy = require(Combat:WaitForChild("BowProjectileConfig"))

local Controller = {}
local started = false
local flights = {}
local attachedBones = {}
local renderConnection: RBXScriptConnection? = nil
local boneElapsed = 0
local folder: Folder? = nil

local function visualFolder(): Folder
    if folder and folder.Parent then return folder end
    local current = Workspace:FindFirstChild("Game1LocalArrows")
    if current and current:IsA("Folder") then
        folder = current
    else
        folder = Instance.new("Folder")
        folder.Name = "Game1LocalArrows"
        folder.Parent = Workspace
    end
    return folder :: Folder
end

local function frameAt(position: Vector3, direction: Vector3): CFrame
    local up = if math.abs(direction:Dot(Vector3.yAxis)) > 0.98 then Vector3.zAxis else Vector3.yAxis
    return CFrame.lookAt(position, position + direction, up)
end

local function nearestBone(target: Model, at: Vector3): Bone?
    local visual = target:FindFirstChild("Visual") or target:FindFirstChild("ImportedRig") or target
    local nearest: Bone? = nil
    local best = math.huge
    for _, node in ipairs(visual:GetDescendants()) do
        if node:IsA("Bone") then
            local d = (node.TransformedWorldCFrame.Position - at).Magnitude
            if d < best then best, nearest = d, node end
        end
    end
    return nearest
end

local function landscapeModel(part: BasePart): Model?
    local cursor = part.Parent
    while cursor and cursor ~= Workspace do
        if cursor:IsA("Model") and cursor:GetAttribute("LandscapeAuthoringTool") == "Game1LandscapePainter" then
            return cursor
        end
        cursor = cursor.Parent
    end
    return nil
end

-- Native weld for any rigid moving prop. Only bone-driven skinned characters
-- need client frame updates. A static object keeps the anchored cosmetic arrow.
local function weldToPart(visual: Model, hitPart: BasePart)
    local root = visual.PrimaryPart or visual:FindFirstChildWhichIsA("BasePart", true)
    if not root then return end
    for _, part in ipairs(visual:GetDescendants()) do
        if part:IsA("BasePart") then
            part.Anchored = false
            part.CanCollide = false
            part.CanTouch = false
            part.CanQuery = false
            part.Massless = true
            if part ~= root then
                local join = Instance.new("WeldConstraint")
                join.Name = "ArrowVisualWeld"
                join.Part0 = root
                join.Part1 = part
                join.Parent = root
            end
        end
    end
    local join = Instance.new("WeldConstraint")
    join.Name = "ArrowVisualWeld"
    join.Part0 = hitPart
    join.Part1 = root
    join.Parent = root
end

local function finish(entry: any)
    local visual: Model = entry.visual
    if not visual.Parent then return end
    local part: BasePart? = entry.hitPart
    local localContact: Vector3? = entry.hitLocal
    -- Never invent a surface from an actor's broad hitbox or its root pivot.
    if not part or not part:IsA("BasePart") or not part.Parent
        or typeof(localContact) ~= "Vector3" then
        visual:Destroy()
        return
    end
    local contact = part.CFrame:PointToWorldSpace(localContact)
    local chosenBone: Bone? = nil
    if entry.target and entry.target.Parent and entry.hitBone and entry.hitBone:IsA("Bone")
        and entry.hitBone.Parent and typeof(entry.hitBoneLocal) == "Vector3" then
        -- Server captured a hitbox bone BEFORE damage triggered the Death pose;
        -- use that bone's actual local visual pose at the end of the flight.
        chosenBone = entry.hitBone
        contact = chosenBone.TransformedWorldCFrame:PointToWorldSpace(entry.hitBoneLocal)
    end
    -- A target that has travelled far from the frozen aim point was missed by
    -- the cosmetic flight. Do not visibly teleport the arrow across the map.
    if (contact - entry.point).Magnitude > Policy.MaxVisualAttachmentJump then
        visual:Destroy()
        return
    end
    local frame = Factory.ContactFrame(visual, contact, entry.direction,
        entry.penetrationStuds, part)
    Factory.Place(visual, frame, entry.correction)
    local target: Model? = entry.target
    if target and target.Parent then
        local bone = chosenBone or nearestBone(target, contact)
        if not bone then
            -- No reliable rig attachment: hide rather than let it float after Death.
            visual:Destroy()
            return
        end
        -- The CLIENT sees the actual animated Death pose. Take the local frame
        -- here, not from the server's potentially different Bone.Transform.
        local relative = bone.TransformedWorldCFrame:ToObjectSpace(visual:GetPivot())
        table.insert(attachedBones, {
            visual = visual,
            bone = bone,
            localFrame = relative,
            expires = os.clock() + Policy.StuckLifetime,
        })
    else
        local sway = landscapeModel(part)
        if sway then
            -- LandscapeSwayController uses Model:PivotTo on this parent, so its
            -- child arrow follows without a second per-frame animation loop.
            visual.Parent = sway
        elseif part.Anchored then
            -- Fixed world surface: leave anchored for a short visual lifetime.
        else
            weldToPart(visual, part)
        end
        Debris:AddItem(visual, Policy.StuckLifetime)
    end
end

local function step(dt: number)
    local now = Workspace:GetServerTimeNow()
    for index = #flights, 1, -1 do
        local entry = flights[index]
        local visual = entry.visual
        if not visual.Parent then
            table.remove(flights, index)
        else
            local t = math.clamp((now - entry.launchedAt) / entry.duration, 0, 1)
            local position = entry.origin:Lerp(entry.point, t)
            Factory.Place(visual, frameAt(position, entry.direction), entry.correction)
            if t >= 1 then
                table.remove(flights, index)
                finish(entry)
            end
        end
    end
    boneElapsed += dt
    if boneElapsed >= Policy.BoneFollowStep then
        boneElapsed %= Policy.BoneFollowStep
        local clock = os.clock()
        for index = #attachedBones, 1, -1 do
            local entry = attachedBones[index]
            if clock >= entry.expires or not entry.bone.Parent or not entry.visual.Parent then
                entry.visual:Destroy()
                table.remove(attachedBones, index)
            else
                entry.visual:PivotTo(entry.bone.TransformedWorldCFrame * entry.localFrame)
            end
        end
    end
    if #flights == 0 and #attachedBones == 0 and renderConnection then
        renderConnection:Disconnect()
        renderConnection = nil
    end
end

local function accept(payload: any)
    if type(payload) ~= "table" or payload.schemaVersion ~= 1
        or typeof(payload.origin) ~= "Vector3" or typeof(payload.point) ~= "Vector3"
        or type(payload.duration) ~= "number" or type(payload.launchedAt) ~= "number" then return end
    if Workspace:GetServerTimeNow() - payload.launchedAt > payload.duration + Policy.StuckLifetime then return end
    local span = payload.point - payload.origin
    if span.Magnitude <= 0.01 or payload.duration <= 0 then return end
    local slug = tostring(payload.arrowSlug or "")
    local catalog = require(ReplicatedStorage:WaitForChild("Game1Shared")
        :WaitForChild("weapon"):WaitForChild("ArrowRegistry"))
    local row = catalog.arrows and catalog.arrows[slug] or nil
    local visual, correction = Factory.Create(row, slug, frameAt(payload.origin, span.Unit), visualFolder())
    table.insert(flights, {
        visual = visual,
        correction = correction,
        origin = payload.origin,
        point = payload.point,
        direction = span.Unit,
        duration = payload.duration,
        launchedAt = payload.launchedAt,
        hitPart = payload.hitPart,
        hitLocal = payload.hitLocal,
        hitBone = payload.hitBone,
        hitBoneLocal = payload.hitBoneLocal,
        target = payload.target,
        penetrationStuds = payload.penetrationStuds,
    })
    while #flights + #attachedBones > Policy.MaxClientVisuals do
        local oldest = table.remove(flights, 1)
        if oldest then
            oldest.visual:Destroy()
        else
            local previous = table.remove(attachedBones, 1)
            if previous then previous.visual:Destroy() end
        end
    end
    if not renderConnection then renderConnection = RunService.RenderStepped:Connect(step) end
end

function Controller.Start()
    if started then return end
    started = true
    local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
    remotes:WaitForChild("BowShotVisual").OnClientEvent:Connect(accept)
end

return table.freeze(Controller)
