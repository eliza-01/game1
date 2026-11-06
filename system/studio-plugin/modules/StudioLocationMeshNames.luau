-- One narrow authoring naming policy for the single-visual Location Asset case.
-- Published asset binaries, collider names and multi-mesh rig topology stay immutable.
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local Naming = {}

function Naming.SingleVisual(root: Instance): MeshPart?
    local found: MeshPart? = nil
    for _, item in ipairs(root:GetDescendants()) do
        if item:IsA("MeshPart") and not Physics.IsCollider(item.Name)
            and item:GetAttribute("Game1DecoPhysicsOnly") ~= true then
            if found then return nil end
            found = item
        end
    end
    return found
end

function Naming.Normalize(root: Instance, slug: string): (MeshPart?, string?)
    local part = Naming.SingleVisual(root)
    if not part or part.Name == slug then return nil, nil end
    local oldName = part.Name
    part.Name = slug
    return part, oldName
end

return Naming
