--!strict
-- Generic full-frame placement by model pivot. Use when the authored Model
-- pivot is the attachment contract and no inner socket should be resolved.
local SocketFacing = require(script.Parent.Parent.world.SocketFacing)
local Mount = {}

local function frame(socket: Attachment): CFrame
    local isBone = socket:IsA("Bone")
    return SocketFacing.FullFrame(if isBone then (socket :: Bone).TransformedWorldCFrame else socket.WorldCFrame, isBone)
end

local function matches(a: CFrame, b: CFrame): boolean
    return (a.Position - b.Position).Magnitude <= 0.001
        and a.LookVector:Dot(b.LookVector) >= 0.99999
        and a.UpVector:Dot(b.UpVector) >= 0.99999
end

function Mount.Align(model: Model, target: Attachment): (boolean, string?)
    if not target.Parent then return false, "missing_target" end
    local targetFrame = frame(target)
    model:PivotTo(targetFrame)
    if not matches(model:GetPivot(), targetFrame) then return false, "alignment_failed" end
    return true, nil
end

return table.freeze(Mount)
