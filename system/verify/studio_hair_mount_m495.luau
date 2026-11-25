-- Studio Play, Server Command Bar. No published assets required.
local Mount = require(game:GetService("ReplicatedStorage").Game1Shared.rig.BoneModelMount)
local actor = Instance.new("Model")
local ok, reason = pcall(function()
    local imported = Instance.new("Model")
    imported.Name = "ImportedRig"
    imported.Parent = actor
    local decoy = Instance.new("MeshPart")
    decoy.Parent = imported
    local wrong = Instance.new("Bone")
    wrong.Name = "hair_mount"
    wrong.Parent = decoy
    local carrier = Instance.new("MeshPart")
    carrier.Name = "rig_carrier"
    carrier.Parent = imported
    local socket = Instance.new("Bone")
    socket.Name = "hair_mount"
    socket.Parent = carrier
    assert(Mount.FindHairBone(actor, "hair_mount") == socket, "wrong carrier")
    local group = Instance.new("Model")
    group.Name = "CharacterHairComponent"
    group:SetAttribute("Game1HairCompound", true)
    group.Parent = imported
    local root = Instance.new("MeshPart")
    root.Anchored = true
    root.CFrame = CFrame.new(3, 4, 5) * CFrame.Angles(0.1, 0.2, 0.3)
    root:SetAttribute("Game1HairAttachment", true)
    root.Parent = group
    group.PrimaryPart = root
    local extra = Instance.new("MeshPart")
    extra.Anchored = true
    extra.CFrame = root.CFrame * CFrame.new(0.2, 0.6, -0.1) * CFrame.Angles(0.2, -0.3, 0.1)
    extra.Parent = group
    local grip = Mount.CreateGrip(root, "CharacterMount", root:GetPivot().Position)
    Mount.CaptureHairOffsets(group, grip)
    local relative = root.CFrame:ToObjectSpace(extra.CFrame)
    local target = CFrame.new(50, 20, 10) * CFrame.Angles(0.3, 1.2, -0.5)
    local function equal(a, b)
        local d = a:ToObjectSpace(b)
        local _, angle = d:ToAxisAngle()
        return d.Position.Magnitude < 0.001 and math.abs(angle) < 0.001
    end
    assert(Mount.Place(group, grip, target))
    assert(equal(grip.WorldCFrame, target))
    assert(equal(root.CFrame:ToObjectSpace(extra.CFrame), relative))
    extra.CFrame = extra.CFrame * CFrame.new(8, 0, 0)
    assert(Mount.Place(group, grip, target)) -- root grip was already correct
    assert(equal(root.CFrame:ToObjectSpace(extra.CFrame), relative), "displaced extra not repaired")
    extra.Parent = actor
    assert(not Mount.HairReady(group) and not Mount.Place(group, grip, target), "accepted incomplete compound")
    extra.Parent = group
    assert(Mount.Place(group, grip, target))
    assert(equal(root.CFrame:ToObjectSpace(extra.CFrame), relative), "late extra not repaired")
    local clone = actor:Clone()
    clone.Parent = actor
    local copy = clone.ImportedRig:FindFirstChild(group.Name)
    assert(copy and copy:IsA("Model") and Mount.HairReady(copy), "clone lost mount metadata")
end)
actor:Destroy()
assert(ok, tostring(reason))
print("[m495] hair carrier, offsets, late extra, clone: OK")
