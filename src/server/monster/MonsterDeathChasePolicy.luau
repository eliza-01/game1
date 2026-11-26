-- Death Chase uses a fixed authored territory, never a moving radius around a player.
local CollectionService = game:GetService("CollectionService")
local Workspace = game:GetService("Workspace")
local Policy = {}
local TAG = "Game1MonsterZone"

local function contains(frame: CFrame, size: Vector3, point: Vector3): boolean
    local p = frame:PointToObjectSpace(point)
    return math.abs(p.X) <= size.X/2 and math.abs(p.Y) <= size.Y/2 and math.abs(p.Z) <= size.Z/2
end

function Policy.Configure(model: Model, record: any, enabled: boolean)
    -- Guided/group fights and the calibration annex retain their existing leash.
    if record.testOwner and (record.testKind ~= "zone" or (record.testZone or 99) > 6) then enabled = false end
    model:SetAttribute("MonsterDeathChase", enabled)
    model:SetAttribute("MonsterDeathChaseZoneFrame", nil)
    model:SetAttribute("MonsterDeathChaseZoneSize", nil)
    if not enabled then return end
    local frame, size = record.testZoneFrame, record.testZoneSize
    if not record.testOwner then
        local origin = model:GetAttribute("MonsterSpawnCenter")
        if typeof(origin) ~= "Vector3" then return end
        -- Require an unambiguous authored zone. Missing or overlapping zones
        -- deliberately retain the normal leash rather than chase indefinitely.
        for _, zone in ipairs(CollectionService:GetTagged(TAG)) do
            if zone:IsA("BasePart") and zone:IsDescendantOf(Workspace) and contains(zone.CFrame, zone.Size, origin) then
                if frame ~= nil then return end
                frame, size = zone.CFrame, zone.Size
            end
        end
    end
    if typeof(frame) == "CFrame" and typeof(size) == "Vector3" then
        model:SetAttribute("MonsterDeathChaseZoneFrame", frame)
        model:SetAttribute("MonsterDeathChaseZoneSize", size)
    end
end

function Policy.IsBound(model: Model): boolean
    return model:GetAttribute("MonsterDeathChase") == true
        and typeof(model:GetAttribute("MonsterDeathChaseZoneFrame")) == "CFrame"
        and typeof(model:GetAttribute("MonsterDeathChaseZoneSize")) == "Vector3"
end

function Policy.AllowsPosition(model: Model, position: Vector3): boolean
    if not Policy.IsBound(model) then return true end
    return contains(model:GetAttribute("MonsterDeathChaseZoneFrame"), model:GetAttribute("MonsterDeathChaseZoneSize"), position)
end

return table.freeze(Policy)
