local Workspace = game:GetService("Workspace")

local EnvironmentAssetService = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("EnvironmentAssetService"))

local WeaponEnvironmentCollision = {}

local filterRevision = -1
local blockingCount = 0
local rayParams = RaycastParams.new()
local overlapQueryParams = OverlapParams.new()
local overlapProbe: Part? = nil
rayParams.FilterType = Enum.RaycastFilterType.Include
rayParams.IgnoreWater = true
overlapQueryParams.FilterType = Enum.RaycastFilterType.Include
overlapQueryParams.MaxParts = 32

local function refreshFilters(): boolean
    local registeredModels, revision = EnvironmentAssetService.GetRegisteredSnapshot()
    if revision == filterRevision then
        return blockingCount > 0
    end

    local blockingModels = {}
    for _, model in ipairs(registeredModels) do
        local definition = EnvironmentAssetService.GetDefinition(model)
        if definition and definition.destructible ~= true then
            table.insert(blockingModels, model)
        end
    end
    rayParams.FilterDescendantsInstances = blockingModels
    overlapQueryParams.FilterDescendantsInstances = blockingModels
    blockingCount = #blockingModels
    filterRevision = revision
    return blockingCount > 0
end

local function queryProbe(): Part
    local current = overlapProbe
    if current and current.Parent == Workspace then
        return current
    end

    local probe = Instance.new("Part")
    probe.Name = "_Game1WeaponEnvironmentProbe"
    probe.Anchored = true
    probe.CanCollide = false
    probe.CanTouch = false
    probe.CanQuery = false
    probe.CastShadow = false
    probe.Transparency = 1
    probe.Archivable = false
    probe.Size = Vector3.one
    probe.Parent = Workspace
    overlapProbe = probe
    return probe
end

local function contactFromPart(part: BasePart, volume: any): (Vector3, Vector3)
    local origin = if typeof(volume.weaponBonePosition) == "Vector3" then volume.weaponBonePosition else volume.cframe.Position
    local direction = if typeof(volume.direction) == "Vector3" and volume.direction.Magnitude > 1e-6
        then volume.direction.Unit
        else volume.cframe.LookVector
    local distance = math.max(0.01, tonumber(volume.bladeLength) or 0) + math.max(0, tonumber(volume.extension) or 0)

    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Include
    params.FilterDescendantsInstances = { part }
    params.IgnoreWater = true
    local ray = Workspace:Raycast(origin, direction * distance, params)
    if ray then
        return ray.Position, ray.Normal
    end

    local contact = part.Position
    pcall(function()
        contact = part:GetClosestPointOnSurface(volume.cframe.Position)
    end)
    local normal = volume.cframe.Position - contact
    if normal.Magnitude <= 1e-5 then
        normal = -direction
    end
    return contact, normal.Unit
end

local function resolveHit(part: BasePart, position: Vector3, normal: Vector3): any?
    local model, definition = EnvironmentAssetService.ResolvePart(part)
    if not model or not definition or definition.destructible == true then
        return nil
    end
    return {
        model = model,
        definition = definition,
        part = part,
        position = position,
        normal = if normal.Magnitude > 1e-6 then normal.Unit else Vector3.yAxis,
    }
end

function WeaponEnvironmentCollision.Query(previousVolume: any?, currentVolume: any): any?
    if type(currentVolume) ~= "table" or typeof(currentVolume.cframe) ~= "CFrame" or typeof(currentVolume.size) ~= "Vector3" then
        return nil
    end
    if not refreshFilters() then
        return nil
    end

    -- Translation uses Blockcast so the first physical collision on the swept
    -- weapon box is authoritative. Roblox shapecasts intentionally ignore an
    -- overlap that already exists at the starting pose, so the exact-volume
    -- GetPartsInPart query below covers first-sample and rotation-only contact.
    if type(previousVolume) == "table" and typeof(previousVolume.cframe) == "CFrame" then
        local displacement = currentVolume.cframe.Position - previousVolume.cframe.Position
        if displacement.Magnitude > 1e-4 then
            local castSize = Vector3.new(
                math.max(previousVolume.size.X, currentVolume.size.X),
                math.max(previousVolume.size.Y, currentVolume.size.Y),
                math.max(previousVolume.size.Z, currentVolume.size.Z)
            )
            local hit = Workspace:Blockcast(previousVolume.cframe, castSize, displacement, rayParams)
            if hit and hit.Instance and hit.Instance:IsA("BasePart") then
                local resolved = resolveHit(hit.Instance, hit.Position, hit.Normal)
                if resolved then
                    return resolved
                end
            end
        end
    end

    local probe = queryProbe()
    probe.Size = currentVolume.size
    probe.CFrame = currentVolume.cframe
    local candidates = Workspace:GetPartsInPart(probe, overlapQueryParams)
    if #candidates == 0 then
        return nil
    end

    local best = nil
    local bestDistance = math.huge
    local reference = if typeof(currentVolume.weaponBonePosition) == "Vector3"
        then currentVolume.weaponBonePosition
        else currentVolume.cframe.Position
    for _, part in ipairs(candidates) do
        local model, definition = EnvironmentAssetService.ResolvePart(part)
        if model and definition and definition.destructible ~= true then
            local position, normal = contactFromPart(part, currentVolume)
            local distance = (position - reference).Magnitude
            if distance < bestDistance then
                bestDistance = distance
                best = {
                    model = model,
                    definition = definition,
                    part = part,
                    position = position,
                    normal = normal,
                }
            end
        end
    end
    return best
end

return table.freeze(WeaponEnvironmentCollision)
