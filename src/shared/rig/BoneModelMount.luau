--!strict
-- One-shot alignment for authored props and equipment assembly; never a frame loop.
local BoneModelMount = {}

local function aligned(actual: CFrame, target: CFrame): boolean
    local errorFrame = target:ToObjectSpace(actual)
    return errorFrame.Position.Magnitude <= 0.0001
        and errorFrame.LookVector:Dot(Vector3.new(0, 0, -1)) >= 0.9999999
        and errorFrame.UpVector:Dot(Vector3.yAxis) >= 0.9999999
end

function BoneModelMount.Place(model: Model, grip: Attachment, socketFrame: CFrame): boolean
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
