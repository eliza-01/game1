-- Studio Play / server Command Bar. M496: direct imported bone frame.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Mount = require(Shared.rig.PivotSocketMount)
local host = Instance.new("MeshPart")
host.Anchored = true
host.CFrame = CFrame.new(5, 20, 3) * CFrame.Angles(0.2, 0.4, -0.5)
host.Parent = workspace
local bone = Instance.new("Bone")
bone.CFrame = CFrame.new(1, 2, 3) * CFrame.Angles(math.rad(20), math.rad(30), math.rad(40))
bone.Parent = host
bone.Transform = CFrame.new(0.1, -0.2, 0.3) * CFrame.Angles(0.2, 0.4, 0.1)
local model = Instance.new("Model")
local carrier = Instance.new("Part")
carrier.Anchored = true
carrier.CFrame = CFrame.new(12, 3, 7)
carrier.Parent = model
model.PrimaryPart = carrier
local part = Instance.new("Part")
part.Anchored = true
part.CFrame = CFrame.new(12, 6, 5) * CFrame.Angles(0.2, 0.5, 0.7)
part.PivotOffset = CFrame.new(0, 2, 0) * CFrame.Angles(0, 0, 0.3)
part.Parent = model
local function close(a, b)
    return (a.Position - b.Position).Magnitude < 0.001
        and a.LookVector:Dot(b.LookVector) > 0.99999
        and a.UpVector:Dot(b.UpVector) > 0.99999
end
local ok, err = pcall(function()
    local relative = carrier.CFrame:ToObjectSpace(part.CFrame)
    local offset = part.PivotOffset
    for _, pose in ipairs({bone.CFrame, CFrame.new(1, 2, 3), CFrame.new(4, 2, 1) * CFrame.Angles(1.2, 2.1, -0.4)}) do
        bone.CFrame = pose
        local frame = bone.TransformedWorldCFrame
        assert(Mount.Align(model, bone, part))
        local actual = part:GetPivot()
        assert((actual.Position - frame.Position).Magnitude < 0.001)
        assert(actual.LookVector:Dot(frame.LookVector) > 0.99999)
        assert(actual.UpVector:Dot(frame.UpVector) > 0.99999)
        assert(actual.RightVector:Dot(frame.RightVector) > 0.99999)
        assert(model.PrimaryPart == carrier and part.PivotOffset == offset)
        assert(close(relative, carrier.CFrame:ToObjectSpace(part.CFrame)))
    end
    local attachment = Instance.new("Attachment")
    attachment.CFrame = CFrame.new(3, 4, 5) * CFrame.Angles(0.3, 0.4, -0.1)
    attachment.Parent = host
    assert(Mount.Align(model, attachment, part))
    assert(close(part:GetPivot(), attachment.WorldCFrame))
end)
model:Destroy()
host:Destroy()
assert(ok, err)
print("m496 direct bone rotation and visual origin smoke passed")
