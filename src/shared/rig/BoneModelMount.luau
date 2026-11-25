--!strict
-- One rigid Bone-socket contract for weapons and compound pivot hair.
-- All model pieces are anchored; the client updates rigid socket transforms.
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

-- An assembled actor has one authoritative skeleton. Do not select a
-- same-named bone from a skinned accessory while the carrier is replicating.
function BoneModelMount.FindHairBone(character: Model, boneName: string): Bone?
    local visual = character:FindFirstChild("Visual") or character
    local imported = visual:FindFirstChild("ImportedRig") or visual
    local carrier = imported:FindFirstChild("rig_carrier")
    if not carrier or not carrier:IsA("MeshPart") then return nil end
    local bone = carrier:FindFirstChild(boneName, true)
    return if bone and bone:IsA("Bone") then bone else nil
end

-- Capture authored relative transforms once, on the complete server-side
-- compound. Attributes travel with clones and streamed pieces; never derive
-- these offsets from a partially replicated or already displaced assembly.
function BoneModelMount.CaptureHairOffsets(model: Model, grip: Attachment)
    local frame = grip.WorldCFrame
    local count = 0
    for _, piece in model:GetChildren() do
        if piece:IsA("BasePart") then
            piece:SetAttribute("Game1HairGripOffset", frame:ToObjectSpace(piece.CFrame))
            count += 1
        end
    end
    model:SetAttribute("Game1HairPieceCount", count)
end

function BoneModelMount.HairReady(model: Model): boolean
    local count = model:GetAttribute("Game1HairPieceCount")
    local root = model.PrimaryPart
    if model:GetAttribute("Game1HairCompound") ~= true or type(count) ~= "number" or count < 1
        or not root or root.Parent ~= model or root:GetAttribute("Game1HairAttachment") ~= true then return false end
    local grip = root:FindFirstChild("CharacterMount")
    if not grip or not grip:IsA("Attachment") then return false end
    local found = 0
    for _, piece in model:GetChildren() do
        if piece:IsA("BasePart") then
            if typeof(piece:GetAttribute("Game1HairGripOffset")) ~= "CFrame" then return false end
            found += 1
        end
    end
    return found == count
end

local function aligned(actual: CFrame, target: CFrame): boolean
    local errorFrame = target:ToObjectSpace(actual)
    return errorFrame.Position.Magnitude <= 0.0001
        and errorFrame.LookVector:Dot(Vector3.new(0, 0, -1)) >= 0.9999999
        and errorFrame.UpVector:Dot(Vector3.yAxis) >= 0.9999999
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

function BoneModelMount.Place(model: Model, grip: Attachment, socketFrame: CFrame): boolean
    if model:GetAttribute("Game1HairCompound") == true then
        if not BoneModelMount.HairReady(model) then return false end
        -- Absolute placement of every piece, even when the root grip is already
        -- aligned. Repairs independently arriving or displaced extras.
        for _, piece in model:GetChildren() do
            if piece:IsA("BasePart") then
                local target = socketFrame * (piece:GetAttribute("Game1HairGripOffset") :: CFrame)
                if not aligned(piece.CFrame, target) then piece.CFrame = target end
            end
        end
        return true
    end
    -- Exact weapon alignment: world-grip -> target socket, applied to whole Model.
    -- Do not dirty anchored parts when the socket is already aligned (e.g.
    -- parked/dead actors). Compare the actual grip, not a cached target: a
    -- streamed/replaced or externally repositioned mount must be corrected.
    local gripFrame = grip.WorldCFrame
    if aligned(gripFrame, socketFrame) then return true end
    local delta = socketFrame * gripFrame:Inverse()
    model:PivotTo(delta * model:GetPivot())
    return true
end

function BoneModelMount.CreateGrip(part: BasePart, name: string, point: Vector3): Attachment
    local grip = Instance.new("Attachment")
    grip.Name = name
    grip.CFrame = part.CFrame:ToObjectSpace(CFrame.new(point))
    grip.Parent = part
    return grip
end

return table.freeze(BoneModelMount)
