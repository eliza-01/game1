--!strict
-- Exact rigid mounting for imported props. A published FBX may retain the
-- socket on its visual mesh rather than its carrier. Never invent a grip.
local BoneModelMount = require(script.Parent.BoneModelMount)
local SocketFacing = require(script.Parent.Parent.world.SocketFacing)
local Mount = {}

local function frame(socket: Attachment): CFrame
    local isBone = socket:IsA("Bone")
    return SocketFacing.FullFrame(if isBone then (socket :: Bone).TransformedWorldCFrame else socket.WorldCFrame, isBone)
end

local function matches(a: CFrame, b: CFrame): boolean
    return (a.Position - b.Position).Magnitude <= 0.001
        and a.LookVector:Dot(b.LookVector) >= 0.99999
        and a.UpVector:Dot(b.UpVector) >= 0.99999
end

local function findGrip(model: Model, reference: BasePart, name: string): (Attachment?, string?)
    -- Prefer the authored carrier when it actually contains the socket. Other
    -- meshes can have independent copies of the same skeleton.
    local primary: Attachment? = nil
    local other: Attachment? = nil
    local conflicting = false
    for _, item in ipairs(model:GetDescendants()) do
        if item.Name == name and item:IsA("Attachment") then
            if item:IsDescendantOf(reference) then
                if primary then return nil, "ambiguous_primary_grip" end
                primary = item
            elseif not other then
                other = item
            elseif not matches(frame(other), frame(item)) then
                conflicting = true
            end
        end
    end
    if primary then return primary, nil end
    if conflicting then return nil, "conflicting_visual_grips" end
    if not other then return nil, "missing_authored_grip" end
    return other, nil
end

function Mount.Align(model: Model, sourceSocket: string, target: Attachment): (boolean, string?)
    local reference = model.PrimaryPart
    if not reference then return false, "missing_primary_part" end
    if not target.Parent then return false, "missing_target" end
    local hole, problem = findGrip(model, reference, sourceSocket)
    if not hole then return false, problem end
    local targetFrame = frame(target)
    local grip = Instance.new("Attachment")
    grip.CFrame = reference.CFrame:ToObjectSpace(frame(hole))
    grip.Parent = reference
    BoneModelMount.Place(model, grip, targetFrame)
    local aligned = matches(grip.WorldCFrame, targetFrame) and matches(frame(hole), targetFrame)
    grip:Destroy()
    if not aligned then return false, "alignment_failed" end
    return true, nil
end

return table.freeze(Mount)
