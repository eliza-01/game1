-- M351: provenance-based placement frame and manual MeshPart.Size transfer.
-- The old instance is READ ONLY. Never copy the old PivotOffset to the new
-- publication, and never interpret Model:GetScale() as a child's manual Size.
-- Handles verified single-visual static placements. Refuses unprovable edits.
local History = require(script.Parent.StudioPublishedMeshHistory)
local Carrier = require(script.Parent.StudioLocationRigCarrier)
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local Legacy = {}

local AXES = {Vector3.xAxis, Vector3.yAxis, Vector3.zAxis}
local function visualParts(model: Model): {MeshPart}
    local found = {}
    for _, part in ipairs(model:GetDescendants()) do
        if part:IsA("MeshPart") and not Carrier.IsCarrier(part)
            and not Physics.IsCollider(part.Name)
            and part:GetAttribute("Game1DecoPhysicsOnly") ~= true then
            table.insert(found,part)
        end
    end
    return found
end
local function sameFrame(a: CFrame,b: CFrame): boolean
    return (a.Position-b.Position).Magnitude <= 0.025
        and a.LookVector:Dot(b.LookVector) >= 0.9999
        and a.UpVector:Dot(b.UpVector) >= 0.9999
end
local function finiteRatio(r: number): boolean
    return r == r and r >= 0.001 and r <= 1000
end
local function ratios(actual: Vector3, authored: Vector3): Vector3
    if authored.X <= 0.001 or authored.Y <= 0.001 or authored.Z <= 0.001 then
        error("Invalid published source MeshPart Size")
    end
    local r = Vector3.new(actual.X/authored.X, actual.Y/authored.Y, actual.Z/authored.Z)
    if not finiteRatio(r.X) or not finiteRatio(r.Y) or not finiteRatio(r.Z) then
        error("Invalid legacy MeshPart.Size ratios; Place unchanged")
    end
    return r
end
local function changed(r: Vector3): boolean
    return math.abs(r.X-1)>0.002 or math.abs(r.Y-1)>0.002
        or math.abs(r.Z-1)>0.002
end

-- The geometry CFrame, unlike MeshPart:GetPivot(), is unaffected by
-- historical managed-rig operations that rewrite PivotOffset. The published
-- Model pivot is therefore transported using the unique proven visual mesh.
function Legacy.Inspect(placed: Model,published: Model): any
    local authored = visualParts(published)
    local existing = visualParts(placed)
    if #authored == 0 or #existing == 0 or #authored ~= #existing then
        error("Historical visual inventory is not sufficient for safe Replace")
    end
    local scale = placed:GetScale()/published:GetScale()
    if not finiteRatio(scale) then error("Invalid historical Model scale") end
    if #authored ~= 1 then
        -- Multipart/skinned models can be replaced using their current Model
        -- pivot, but untracked manually resized meshes may NOT be discarded.
        local counts = {}
        for _, part in ipairs(authored) do
            local id = History.Id(part.MeshId)
            counts[id] = counts[id] or {}
            table.insert(counts[id],part.Size*scale)
        end
        for _, part in ipairs(existing) do
            local id=History.Id(part.MeshId)
            local list=counts[id]
            if not list or #list==0 then error("Historical mesh inventory changed") end
            local foundIndex=nil
            for index,size in ipairs(list) do
                if (part.Size-size).Magnitude <= 0.025 then foundIndex=index; break end
            end
            if not foundIndex then
                error("Manually resized multipart Location rig; cannot safely replace without a dedicated mapping")
            end
            table.remove(list,foundIndex)
        end
        return {frame=placed:GetPivot(), resized=false, rebased=false}
    end
    local reference,old = authored[1],existing[1]
    if History.Id(reference.MeshId) ~= History.Id(old.MeshId) then
        error("Historical visual Mesh ID differs from placed source; Place unchanged")
    end
    local manual = ratios(old.Size,reference.Size*scale)
    -- ScaleTo can legitimately scale a published PivotOffset.Position. Do not
    -- mistake ordinary uniform Model scaling for the historic Sync rebasing.
    local authoredOffset = CFrame.new(reference.PivotOffset.Position * scale)
        * reference.PivotOffset.Rotation
    local pivotRebased = not sameFrame(authoredOffset,old.PivotOffset)
    local recovered = old.CFrame * reference.CFrame:Inverse() * published:GetPivot()
    -- Repair and historical Sync can change only PivotOffset and PrimaryPart,
    -- leaving the visible CFrame unchanged. Reconstruct from source provenance
    -- only when the old part's PivotOffset has actually diverged.
    local placementFrame = if pivotRebased then recovered else placed:GetPivot()
    return {frame=placementFrame, resized=changed(manual), rebased=pivotRebased,
        ratios=manual,
        sourceLocalAxes=published:GetPivot().Rotation:ToObjectSpace(reference.CFrame.Rotation),
        sourceMeshId=History.Id(reference.MeshId),
        pivotShift=(recovered.Position-placed:GetPivot().Position).Magnitude}
end

local function isSimple(target: Model, mesh: MeshPart): boolean
    for _, obj in ipairs(target:GetDescendants()) do
        if obj:IsA("BasePart") and obj ~= mesh then return false end
        if obj:IsA("Bone") or obj:IsA("Attachment") or obj:IsA("JointInstance")
            or obj:IsA("Constraint") or obj:IsA("WeldConstraint")
            or obj:IsA("WrapLayer") or obj:IsA("WrapTarget") then return false end
    end
    return true
end

-- Preserve *stretch factors*, not absolute dimensions of two different meshes.
-- A target can have its own authored dimensions. Re-map axes only where the
-- visual basis of the two published Models proves a 90-degree permutation.
-- Arbitrary basis changes imply shear under non-uniform scaling and are refused.
function Legacy.ResizeTarget(target: Model, geometry: any, dryRun: boolean?)
    if not geometry.resized then return end
    local meshes=visualParts(target)
    if #meshes ~= 1 or not isSimple(target,meshes[1]) then
        error("Manually resized source requires a single, unrigged target MeshPart; Place unchanged")
    end
    local targetPart=meshes[1]
    local targetLocalAxes=target:GetPivot().Rotation:ToObjectSpace(targetPart.CFrame.Rotation)
    local map=geometry.sourceLocalAxes:ToObjectSpace(targetLocalAxes)
    local old={geometry.ratios.X,geometry.ratios.Y,geometry.ratios.Z}
    local mapped={}
    local used={}
    for index,axis in ipairs(AXES) do
        local mappedAxis=map:VectorToWorldSpace(axis)
        local winner,largest=nil,0
        for sourceIndex,sourceAxis in ipairs(AXES) do
            local similarity=math.abs(mappedAxis:Dot(sourceAxis))
            if similarity>largest then winner=sourceIndex; largest=similarity end
        end
        if not winner or largest<0.999 or used[winner] then
            error("Non-uniform legacy Size cannot map between source/target mesh axes without shear")
        end
        used[winner]=true
        mapped[index]=old[winner]
    end
    local newSize=Vector3.new(targetPart.Size.X*mapped[1],
        targetPart.Size.Y*mapped[2],targetPart.Size.Z*mapped[3])
    if newSize.X<=0.001 or newSize.Y<=0.001 or newSize.Z<=0.001
        or newSize.X>4096 or newSize.Y>4096 or newSize.Z>4096 then
        error("Transformed replacement MeshPart.Size exceeds safe bounds")
    end
    if not dryRun then targetPart.Size=newSize end
end

return table.freeze(Legacy)
