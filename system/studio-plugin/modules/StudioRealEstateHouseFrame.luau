-- Author-space transform for all Real Estate Studio sync paths.
-- The MeshPart CFrame tracks its geometry centre, which can shift after an
-- FBX revision. The authored import pivot (CFrame * PivotOffset) is the
-- stable registration frame. Never match replacements by CFrame alone.
local HouseFrame = {}

function HouseFrame.Find(root: Instance): MeshPart?
    local match: MeshPart? = nil
    for _, instance in root:GetDescendants() do
        if instance:IsA("MeshPart") and instance.Name == "house" then
            if match then return nil end
            match = instance
        end
    end
    return match
end

function HouseFrame.Relative(source: MeshPart, target: MeshPart): CFrame
    return target:GetPivot() * source:GetPivot():Inverse()
end

function HouseFrame.Align(rig: Model, sourceAnchor: MeshPart, targetPivot: CFrame, context: string)
    local offset = targetPivot * sourceAnchor:GetPivot():Inverse()
    rig:PivotTo(offset * rig:GetPivot())
    local result = sourceAnchor:GetPivot()
    if (result.Position - targetPivot.Position).Magnitude > 0.025
        or result.LookVector:Dot(targetPivot.LookVector) < 0.9999
        or result.UpVector:Dot(targetPivot.UpVector) < 0.9999 then
        error(context .. ": authored house pivot could not be aligned after Model:PivotTo")
    end
end

return table.freeze(HouseFrame)
