-- Authored house pivot is always the original Model pivot, never a visual
-- MeshPart. All parts and house_armature share this project-space origin.
local HouseFrame={}

function HouseFrame.Find(root: Instance): Model?
    if root:IsA("Model") then return root end
    return nil
end

function HouseFrame.Relative(source: Instance, target: Instance): CFrame
    return target:GetPivot()*source:GetPivot():Inverse()
end

function HouseFrame.Align(rig: Model, sourceAnchor: Instance, targetPivot: CFrame, context: string)
    local delta=targetPivot*sourceAnchor:GetPivot():Inverse()
    rig:PivotTo(delta*rig:GetPivot())
end

return table.freeze(HouseFrame)
