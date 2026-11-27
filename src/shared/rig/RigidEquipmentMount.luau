--!strict
-- Rigid, reusable equipment. Create exactly one animated Bone constraint per
-- item, weld compound pieces once, then let the engine own the pose.
local StaticMount = require(script.Parent.BoneModelMount)
local SocketFacing = require(script.Parent.Parent.world.SocketFacing)
local Mount = {}
local JOINT = "Game1RigidEquipmentJoint"
local GRIP = "Game1RigidEquipmentGrip"
local WELD = "Game1RigidEquipmentPiece"
local ROOT_SOCKET = "Game1RigidEquipmentRootSocket"

-- The old mount contract excludes the authored socket's own Transform.
-- Use its animated parent as the joint endpoint and fold the authored local
-- socket frame into the item-side grip. No extra animated Bone is necessary.
local function endpointFor(target: Bone, create: boolean): Attachment?
    local parent = target.Parent
    if not parent then return nil end
    if parent:IsA("Bone") then return parent end
    if not parent:IsA("BasePart") then return nil end
    -- A top-level socket follows its MeshPart, not its own animated Transform.
    local existing = parent:FindFirstChild(ROOT_SOCKET)
    if existing then
        assert(existing:IsA("Attachment") and not existing:IsA("Bone")
            and existing.CFrame == CFrame.identity, "invalid rigid equipment root endpoint")
        return existing
    end
    if not create then return nil end
    local endpoint = Instance.new("Attachment")
    endpoint.Name = ROOT_SOCKET
    endpoint.CFrame = CFrame.identity
    endpoint.Parent = parent
    return endpoint
end

local function endpointFrame(endpoint: Attachment): CFrame
    return if endpoint:IsA("Bone") then endpoint.TransformedWorldCFrame else endpoint.WorldCFrame
end

local function correction(kind: string): CFrame
    if kind == "hair" then return SocketFacing.FullFrame(CFrame.identity, true) end
    assert(kind == "weapon", "unknown rigid equipment kind")
    return CFrame.Angles(math.rad(-90), 0, 0)
end

function Mount.FindBone(character: Model, name: string): Bone?
    if name == "" then return nil end
    -- Restore the weapon lookup scope used before M607.
    local visual = character:FindFirstChild("Visual") or character:FindFirstChild("ImportedRig") or character
    local bone = visual:FindFirstChild(name, true)
    return if bone and bone:IsA("Bone") then bone else nil
end

local function findHairBone(character: Model, name: string): Bone?
    local visual = character:FindFirstChild("Visual") or character
    local imported = visual:FindFirstChild("ImportedRig") or visual
    local carrier = imported:FindFirstChild("rig_carrier")
    if not carrier or not carrier:IsA("MeshPart") then return nil end
    local bone = carrier:FindFirstChild(name, true)
    return if bone and bone:IsA("Bone") then bone else nil
end

function Mount.SocketFrame(target: Bone, kind: string): CFrame
    local parent = target.Parent
    local frame = if parent and parent:IsA("Bone")
        then parent.TransformedWorldCFrame * target.CFrame
        else target.WorldCFrame
    return frame * correction(kind)
end

function Mount.Attach(model: Model, grip: Attachment, target: Bone, kind: string): RigidConstraint
    local root = grip.Parent
    assert(root and root:IsA("BasePart") and root:IsDescendantOf(model), "equipment grip has no root")
    assert(not target:IsDescendantOf(model), "equipment socket cannot belong to the item")
    -- Remove imported rigid joints: authored relative transforms are the contract.
    -- Bone hierarchies and other visual descendants remain untouched.
    local parts: {BasePart} = {}
    for _, object in model:GetDescendants() do
        if object:IsA("JointInstance") or object:IsA("WeldConstraint") or object:IsA("Constraint") then
            object:Destroy()
        elseif object:IsA("BasePart") then
            object.Anchored = false
            object.CanCollide = false
            object.CanTouch = false
            object.CanQuery = false
            object.Massless = true
            object.RootPriority = -127
            table.insert(parts, object)
        end
    end
    model.PrimaryPart = root
    -- The authored grip is not changed (bow/other geometry consumers use it).
    -- If P is the animated parent frame and L the authored local socket,
    -- desired grip = P * L * correction. A constant inverse offset on the
    -- item makes the native joint satisfy exactly that equation.
    local offset = target.CFrame * correction(kind)
    local socket = assert(endpointFor(target, true), "equipment socket has no valid parent endpoint")
    StaticMount.Place(model, grip, Mount.SocketFrame(target, kind))
    for _, part in parts do
        if part ~= root then
            local weld = Instance.new("WeldConstraint")
            weld.Name = WELD
            weld.Part0 = root
            weld.Part1 = part
            weld.Parent = part
        end
    end
    local jointGrip = Instance.new("Attachment")
    jointGrip.Name = GRIP
    jointGrip.CFrame = grip.CFrame * offset:Inverse()
    jointGrip.Parent = root
    local joint = Instance.new("RigidConstraint")
    joint.Name = JOINT
    joint.Attachment0 = socket
    joint.Attachment1 = jointGrip
    joint:SetAttribute("Game1AuthoredSocketName", target.Name)
    joint:SetAttribute("Game1EquipmentKind", kind)
    joint.Parent = root
    model:SetAttribute("Game1RigidEquipment", true)
    return joint
end

function Mount.HairAssemblyReady(character: Model): boolean
    local visual = character:FindFirstChild("Visual") or character
    local imported = visual:FindFirstChild("ImportedRig") or visual
    local expected = visual:GetAttribute("Game1AssemblyHairPieceCount")
    if type(expected) ~= "number" then return false end
    local hair = imported:FindFirstChild("CharacterHairComponent")
    if expected == 0 then return hair == nil end
    if not hair or not hair:IsA("Model") or hair:GetAttribute("Game1HairPieceCount") ~= expected then return false end
    local root = hair.PrimaryPart
    if not root or root.Parent ~= hair then return false end
    local name = root:GetAttribute("HairTargetBoneName")
    local target = if type(name) == "string" then findHairBone(character, name) else nil
    local joint = root:FindFirstChild(JOINT)
    local grip = root:FindFirstChild(GRIP)
    local socket = if target then endpointFor(target, false) else nil
    if not socket or not grip or not grip:IsA("Attachment") or not joint or not joint:IsA("RigidConstraint")
        or joint.Attachment0 ~= socket or joint.Attachment1 ~= grip then return false end
    local authored = root:FindFirstChild("CharacterMount")
    if not authored or not authored:IsA("Attachment") or not target then return false end
    local expectedGrip = authored.CFrame * (target.CFrame * correction("hair")):Inverse()
    local errorFrame = expectedGrip:ToObjectSpace(grip.CFrame)
    if errorFrame.Position.Magnitude > 0.0001 or errorFrame.LookVector:Dot(Vector3.new(0, 0, -1)) < 0.99999
        or errorFrame.UpVector:Dot(Vector3.yAxis) < 0.99999 then return false end
    local count = 0
    for _, part in hair:GetChildren() do
        if part:IsA("BasePart") then
            count += 1
            if part ~= root then
                local weld = part:FindFirstChild(WELD)
                if not weld or not weld:IsA("WeldConstraint") or weld.Part0 ~= root or weld.Part1 ~= part then return false end
            end
        end
    end
    return count == expected
end

function Mount.IsEquipmentPart(part: BasePart): boolean
    local ancestor = part:FindFirstAncestorWhichIsA("Model")
    while ancestor do
        if ancestor:GetAttribute("Game1RigidEquipment") == true then return true end
        ancestor = ancestor:FindFirstAncestorWhichIsA("Model")
    end
    return false
end

function Mount.GetBowReleaseOrigin(character: Model): Vector3?
    local weapon = character:FindFirstChild("EquippedWeapon")
    if not weapon or not weapon:IsA("Model") or weapon:GetAttribute("WeaponType") ~= "bow" then return nil end
    -- Derive the release point from the animated socket and the authored grip,
    -- not a possibly delayed physics transform of the accessory.
    local root = weapon.PrimaryPart
    local joint = root and root:FindFirstChild(JOINT)
    if not joint or not joint:IsA("RigidConstraint") then return nil end
    local socket, grip = joint.Attachment0, joint.Attachment1
    if not socket or not grip then return nil end
    local delta = endpointFrame(socket) * grip.WorldCFrame:Inverse()
    for _, name in {"ArrowNock", "ArrowRelease", "ArrowSocket"} do
        local node = weapon:FindFirstChild(name, true)
        if node and node:IsA("Bone") then return delta:PointToWorldSpace(node.TransformedWorldCFrame.Position) end
        if node and node:IsA("Attachment") then return delta:PointToWorldSpace(node.WorldPosition) end
    end
    local authored = root and root:FindFirstChild("Game1WeaponGrip")
    return if authored and authored:IsA("Attachment") then delta:PointToWorldSpace(authored.WorldPosition) else nil
end

return table.freeze(Mount)
