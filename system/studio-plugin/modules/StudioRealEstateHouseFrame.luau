-- Author-space transform for all Real Estate Studio sync paths.
-- The MeshPart CFrame tracks its geometry centre, which can shift after an
-- FBX revision. The authored import pivot (CFrame * PivotOffset) is the
-- stable registration frame. Never match replacements by CFrame alone.
local RigSwap = require(script.Parent.StudioManagedRigSwap)
local MeshAnchor = require(script.Parent.StudioAuthoringMeshAnchor)
local HouseFrame = {}

function HouseFrame.Find(root: Instance): MeshPart?
    return MeshAnchor.FindUniqueNamed(root, "house")
end

function HouseFrame.Relative(source: MeshPart, target: MeshPart): CFrame
    return target:GetPivot() * source:GetPivot():Inverse()
end

function HouseFrame.Align(rig: Model, sourceAnchor: MeshPart, targetPivot: CFrame, context: string)
    RigSwap.AlignToAnchor(rig, sourceAnchor, targetPivot, context)
end

return table.freeze(HouseFrame)
