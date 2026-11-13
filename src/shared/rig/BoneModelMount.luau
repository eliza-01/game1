--!strict
-- One rigid Bone-socket contract for weapons and compound pivot hair.
-- All model pieces are anchored; only a client-owned pivot is moved per frame.
-- The server uses the same solver once when building the actor.
local SocketFacing = require(script.Parent.Parent.world.SocketFacing)

local BoneModelMount = {}
local WEAPON_ROTATION = CFrame.Angles(math.rad(-90), 0, 0)

function BoneModelMount.FindBone(character: Model, boneName: string): Bone?
    if boneName == "" then return nil end
    local visual = character:FindFirstChild("Visual") or character:FindFirstChild("ImportedRig") or character
    local candidate = visual:FindFirstChild(boneName, true)
    return if candidate and candidate:IsA("Bone") then candidate else nil
end

function BoneModelMount.SocketFrame(targetBone: Bone, kind: string): CFrame
    -- The authored socket frame deliberately excludes the socket's own
    -- Transform. Both server assembly and the client use the same basis.
    local parent = targetBone.Parent
    local frame = if parent and parent:IsA("Bone")
        then parent.TransformedWorldCFrame * targetBone.CFrame
        else targetBone.WorldCFrame
    if kind == "hair" then
        return SocketFacing.FullFrame(frame, true)
    end
    assert(kind == "weapon", "unknown rigid bone mount kind: " .. kind)
    return frame * WEAPON_ROTATION
end

function BoneModelMount.Place(model: Model, grip: Attachment, socketFrame: CFrame)
    -- Exact weapon alignment: world-grip -> target socket, applied to whole Model.
    local delta = socketFrame * grip.WorldCFrame:Inverse()
    model:PivotTo(delta * model:GetPivot())
end

function BoneModelMount.CreateGrip(part: BasePart, name: string, point: Vector3): Attachment
    local grip = Instance.new("Attachment")
    grip.Name = name
    grip.CFrame = part.CFrame:ToObjectSpace(CFrame.new(point))
    grip.Parent = part
    return grip
end

return table.freeze(BoneModelMount)
