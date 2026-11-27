-- Paste into Studio Command Bar while playing (Client for hero and observed NPC;
-- Server for authoritative NPC). One snapshot only; never installed in Runtime.
local mount = require(game:GetService("ReplicatedStorage").Game1Shared.rig.RigidEquipmentMount)
local function errorBetween(expected, actual)
    local delta = expected:ToObjectSpace(actual)
    local _, angle = delta:ToAxisAngle()
    return string.format("%.4f studs / %.2f deg", delta.Position.Magnitude, math.deg(math.abs(angle)))
end
local count = 0
for _, joint in workspace:GetDescendants() do
    if joint:IsA("RigidConstraint") and joint.Name == "Game1RigidEquipmentJoint" then
        local endpoint, grip = joint.Attachment0, joint.Attachment1
        local name, kind = joint:GetAttribute("Game1AuthoredSocketName"), joint:GetAttribute("Game1EquipmentKind")
        local parent = endpoint and (if endpoint:IsA("Bone") then endpoint else endpoint.Parent)
        local target = parent and type(name) == "string" and parent:FindFirstChild(name)
        local root = grip and grip.Parent
        local authored = root and root:FindFirstChild(if kind == "hair" then "CharacterMount" else "Game1WeaponGrip")
        if target and target:IsA("Bone") and endpoint and grip and authored and authored:IsA("Attachment") then
            count += 1
            local expected = mount.SocketFrame(target, kind)
            local endpointWorld = if endpoint:IsA("Bone") then endpoint.TransformedWorldCFrame else endpoint.WorldCFrame
            local predicted = endpointWorld * grip.WorldCFrame:Inverse() * authored.WorldCFrame
            print("[M609]", root:GetFullName(), "bone", target:GetFullName(),
                "socket animation", errorBetween(target.CFrame, target.CFrame * target.Transform),
                "contract error", errorBetween(expected, predicted),
                "solver error", errorBetween(endpointWorld, grip.WorldCFrame),
                "visual error", errorBetween(expected, authored.WorldCFrame), "active", joint.Active)
        else
            warn("[M609] incomplete equipment endpoint", joint:GetFullName())
        end
    end
end
print("[M609] snapshots", count)
