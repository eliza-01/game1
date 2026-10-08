local DecoTransform = {}

local WORLD_UP = Vector3.yAxis

local function rotationOnly(cframe: CFrame): CFrame
    return CFrame.fromMatrix(Vector3.zero, cframe.XVector, cframe.YVector, cframe.ZVector)
end

local function surfaceFrame(normal: Vector3, cameraLook: Vector3): CFrame
    local up = if normal.Magnitude > 0.001 then normal.Unit else WORLD_UP
    local forward = cameraLook - up * cameraLook:Dot(up)
    if forward.Magnitude < 0.01 then
        local fallback = if math.abs(up.Y) < 0.95 then WORLD_UP else Vector3.zAxis
        forward = fallback - up * fallback:Dot(up)
    end
    return CFrame.lookAt(Vector3.zero, forward.Unit, up)
end

function DecoTransform.authoredPivotRotation(model: Model): CFrame
    return rotationOnly(model:GetPivot())
end

function DecoTransform.previewPivot(model: Model): CFrame
    -- Re-center the model without replacing the imported FBX basis. Roblox can
    -- encode FBX axis conversion in the model/part pivot; forcing identity here
    -- makes otherwise-correct Z-up source assets appear rotated in the viewport.
    return DecoTransform.authoredPivotRotation(model)
end

function DecoTransform.supportOffset(model: Model): number
    -- Measure the lowest rendered part point against Roblox world-up in the
    -- asset's authored pose. This is independent of the model pivot's local axes.
    -- The same offset remains valid after surfaceFrame rotates the whole authored
    -- pose from world-up onto the hit normal.
    local pivot = model:GetPivot()
    local minimum = math.huge
    local hasPart = false

    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") then
            hasPart = true
            local half = descendant.Size * 0.5
            for _, x in ipairs({ -1, 1 }) do
                for _, y in ipairs({ -1, 1 }) do
                    for _, z in ipairs({ -1, 1 }) do
                        local point = descendant.CFrame:PointToWorldSpace(Vector3.new(
                            half.X * x,
                            half.Y * y,
                            half.Z * z
                        ))
                        local height = (point - pivot.Position):Dot(WORLD_UP)
                        minimum = math.min(minimum, height)
                    end
                end
            end
        end
    end

    if not hasPart then
        error("location asset model contains no BasePart geometry")
    end
    return math.max(0, -minimum)
end

function DecoTransform.placementPivot(
    authoredPivotRotation: CFrame,
    targetPosition: Vector3,
    surfaceNormal: Vector3,
    cameraLook: Vector3
): CFrame
    -- surfaceFrame is a delta from canonical Roblox world-up to the requested
    -- surface. authoredPivotRotation is multiplied afterwards so importer-authored
    -- FBX basis compensation is preserved instead of overwritten.
    return CFrame.new(targetPosition) * surfaceFrame(surfaceNormal, cameraLook) * authoredPivotRotation
end

return DecoTransform
