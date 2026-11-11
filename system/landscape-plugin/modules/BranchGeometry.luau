local BranchGeometry = {}

local function stableFrame(startPoint: Vector3, endPoint: Vector3): CFrame
    local direction = (endPoint - startPoint).Unit
    local reference = if math.abs(direction:Dot(Vector3.yAxis)) > 0.94
        then Vector3.xAxis else Vector3.yAxis
    local back = direction:Cross(reference).Unit
    local up = back:Cross(direction).Unit
    return CFrame.fromMatrix((startPoint + endPoint) * 0.5, direction, up, back)
end

function BranchGeometry.Apply(part: Part, from: Vector3, to: Vector3,
    diameter: number, color: Color3, isPreview: boolean)
    local length = (to - from).Magnitude
    if length < 0.001 then
        part.Transparency = 1
        return
    end
    part.Name = "Stem"
    part.Shape = Enum.PartType.Cylinder
    part.Material = Enum.Material.SmoothPlastic
    part.Anchored = true
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = false
    part.CastShadow = not isPreview
    part.Size = Vector3.new(length, diameter, diameter)
    part.CFrame = stableFrame(from, to)
    part.Color = color
    part.Transparency = if isPreview then 0.35 else 0
end

-- Raise the center of the cylinder half its thickness away from the hit face.
-- Keep authored anchors in unmodified world coordinates for later re-authoring.
function BranchGeometry.VisiblePoint(anchor, diameter: number): Vector3
    return anchor.position + anchor.normal * (diameter * 0.5 + 0.015)
end

function BranchGeometry.CreateSegments(container: Instance, anchors, diameter, color, isPreview)
    for index = 1, #anchors - 1 do
        local a = BranchGeometry.VisiblePoint(anchors[index], diameter)
        local b = BranchGeometry.VisiblePoint(anchors[index + 1], diameter)
        if (a - b).Magnitude > 0.001 then
            local part = Instance.new("Part")
            BranchGeometry.Apply(part, a, b, diameter, color, isPreview)
            part.Name = string.format("Stem_%02d", index)
            -- Stored on new strokes for an accurate outward facing when assets
            -- are attached anywhere along a curved surface-following stem.
            if not isPreview then
                part:SetAttribute("LandscapeStemNormalA", anchors[index].normal)
                part:SetAttribute("LandscapeStemNormalB", anchors[index + 1].normal)
            end
            part.Parent = container
        end
    end
end

return BranchGeometry
