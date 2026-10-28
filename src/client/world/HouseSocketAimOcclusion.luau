--!strict
-- LOS check for center-reticle AIM regions. Query the real world, not a
-- generated invisible Part: combat/headshot queries must remain unaffected.
local Workspace = game:GetService("Workspace")
local Occlusion = {}

function Occlusion.IsClear(origin: Vector3, direction: Vector3, entryDistance: number, character: Model?): boolean
    if direction.Magnitude < 0.999 or entryDistance < 0 then return false end
    -- Allow a small boundary tolerance to avoid self-occlusion by a collider
    -- intersecting the outer surface of the invisible AIM region.
    local distance = math.max(0, entryDistance - 0.05)
    if distance <= 0 then return true end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = if character then {character} else {}
    params.IgnoreWater = true
    -- Only one real scene raycast for the nearest geometrically eligible AIM.
    return Workspace:Raycast(origin, direction * distance, params) == nil
end

return table.freeze(Occlusion)
