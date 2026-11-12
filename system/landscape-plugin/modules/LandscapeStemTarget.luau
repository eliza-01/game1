-- Studio-only snapping to authored Landscape Painter stems. Existing M282 stems
-- have CanQuery=false; we intentionally do not modify Place just to pick them.
-- Scanner works on named authored cylinders, never arbitrary Workspace geometry.
local StemTarget = {}

local DECOR_ROOT = "Game1LandscapeDecor"
local MAX_PICK_RADIUS = 1.2
local MIN_PICK_RADIUS = 0.24

local function branchFolder(workspace)
    local root = workspace:FindFirstChild(DECOR_ROOT)
    local folder = if root then root:FindFirstChild("Branches") else nil
    if folder and folder:IsA("Folder") then return folder end
    return nil
end

function StemTarget.IsAuthoredStem(part, folder)
    if not folder or not part:IsA("Part") or part.Shape ~= Enum.PartType.Cylinder
        or part.Name:match("^Stem_%d+$") == nil or not part:IsDescendantOf(folder) then
        return nil
    end
    local branch = part.Parent
    if not branch or not branch:IsA("Model") or branch.Parent ~= folder
        or branch:GetAttribute("AuthoringTool") ~= "Game1LandscapePainter" then
        return nil
    end
    return branch
end

function StemTarget.Collect(workspace)
    local folder = branchFolder(workspace)
    local parts = {}
    if folder then
        for _, branch in ipairs(folder:GetChildren()) do
            if branch:IsA("Model") and branch:GetAttribute("AuthoringTool") == "Game1LandscapePainter" then
                for _, part in ipairs(branch:GetChildren()) do
                    if StemTarget.IsAuthoredStem(part, folder) then
                        table.insert(parts, part)
                    end
                end
            end
        end
    end
    return parts, folder
end

-- Closest point on a finite segment to a camera ray (t>=0, 0<=s<=1).
-- Does not depend on CanQuery or touch/collision state of the segment.
function StemTarget.Closest(rayOrigin: Vector3, rayDirection: Vector3,
    startPoint: Vector3, endPoint: Vector3)
    local segment = endPoint - startPoint
    local lengthSq = segment:Dot(segment)
    if lengthSq < 0.000001 then return nil end
    local direction = rayDirection.Unit
    local offset = startPoint - rayOrigin
    local b = direction:Dot(segment)
    local d = direction:Dot(offset)
    local e = segment:Dot(offset)
    local denominator = lengthSq - b * b
    local s = if denominator > 0.000001
        then math.clamp((b * d - e) / denominator, 0, 1)
        else 0
    local t = math.max(0, d + b * s)
    if t == 0 then
        s = math.clamp((rayOrigin - startPoint):Dot(segment) / lengthSq, 0, 1)
    end
    local onStem = startPoint + segment * s
    return onStem, t, (rayOrigin + direction * t - onStem).Magnitude, s
end

local function outsideNormal(part, branch, fraction: number, tangent: Vector3, rayOrigin: Vector3)
    local a = part:GetAttribute("LandscapeStemNormalA")
    local b = part:GetAttribute("LandscapeStemNormalB")
    if typeof(a) ~= "Vector3" or typeof(b) ~= "Vector3" then
        -- M282/M286 strokes have only model-level endpoint normals.
        a = branch:GetAttribute("StartNormal")
        b = branch:GetAttribute("EndNormal")
    end
    local normal = if typeof(a) == "Vector3" and typeof(b) == "Vector3"
        then a:Lerp(b, fraction) else Vector3.zero
    if normal.Magnitude < 0.01 and typeof(a) == "Vector3" then normal = a end
    -- A cylinder's radial normal must be perpendicular to its axis.
    normal -= tangent * normal:Dot(tangent)
    if normal.Magnitude < 0.01 then
        normal = rayOrigin - part.Position
        normal -= tangent * normal:Dot(tangent)
    end
    if normal.Magnitude < 0.01 then
        normal = part.CFrame.UpVector
    end
    return normal.Unit
end

function StemTarget.Find(parts, folder, unitRay, surfaceHit, maxDistance: number)
    if not folder then return nil end
    local best = nil
    local direction = unitRay.Direction.Unit
    local origin = unitRay.Origin
    -- An authored stem in front of a wall is eligible; a stem behind it isn't.
    local stopDistance = if surfaceHit then (surfaceHit.Position - origin).Magnitude + 0.15
        else maxDistance
    for _, part in ipairs(parts) do
        local branch = StemTarget.IsAuthoredStem(part, folder)
        if branch and part.Size.X >= 0.001 then
            local half = part.Size.X * 0.5
            local tangent = part.CFrame.RightVector
            local a = part.Position - tangent * half
            local b = part.Position + tangent * half
            local onStem, t, distance, fraction = StemTarget.Closest(origin, direction, a, b)
            if onStem and t <= maxDistance and t <= stopDistance then
                -- Clickable radius is larger than the physical 0.05-stud stem.
                -- Approximate a fixed on-screen targeting cone while retaining
                -- wall occlusion and only considering authored stem geometry.
                local tolerance = math.clamp(t * 0.012, MIN_PICK_RADIUS, MAX_PICK_RADIUS)
                    + part.Size.Y * 0.5
                if distance <= tolerance then
                    local score = distance / tolerance
                    if not best or score < best.score - 0.02
                        or (math.abs(score - best.score) <= 0.02 and t < best.t) then
                        local normal = outsideNormal(part, branch, fraction, tangent, origin)
                        local point = onStem + normal * (part.Size.Y * 0.5 + 0.005)
                        best = {
                            Position = point, Normal = normal,
                            kind = "stem", stem = part, branch = branch,
                            score = score, t = t,
                        }
                    end
                end
            end
        end
    end
    return best
end

return table.freeze(StemTarget)
