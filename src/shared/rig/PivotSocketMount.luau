--!strict
-- Rigid Bone Socket: match the imported socket's HEAD and world rotation.
-- Both the imported MeshPart pivot and Bone already use Roblox CFrames.
-- Do not apply another Blender-to-Roblox axis conversion at mount time.
local Mount = {}

function Mount.TargetFrame(socket: Attachment): CFrame
    if socket:IsA("Bone") then
        return (socket :: Bone).TransformedWorldCFrame
    end
    return socket.WorldCFrame
end

local function matches(a: CFrame, b: CFrame): boolean
    return (a.Position - b.Position).Magnitude <= 0.001
        and a.LookVector:Dot(b.LookVector) >= 0.99999
        and a.UpVector:Dot(b.UpVector) >= 0.99999
end

function Mount.Align(model: Model, target: Attachment, origin: BasePart): (boolean, string?)
    if not target.Parent then return false, "missing_target" end
    if not origin:IsDescendantOf(model) then return false, "missing_origin" end
    local targetFrame = Mount.TargetFrame(target)
    -- Move the entire assembly by the selected object's pivot delta. The
    -- rig_carrier stays PrimaryPart and its native PivotOffset is untouched.
    local delta = targetFrame * origin:GetPivot():Inverse()
    model:PivotTo(delta * model:GetPivot())
    if not matches(origin:GetPivot(), targetFrame) then return false, "alignment_failed" end
    return true, nil
end

return table.freeze(Mount)
