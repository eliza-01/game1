--!strict
-- Pure geometry in the authored origin frame. No spawning or AI state.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local CharacterConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local Layout = {}
function Layout.Build(origin: CFrame, rows: {any}, maxLevel: number, spacing: number, size: Vector3, maxGroup: number)
    local columns = math.ceil(maxLevel / 2)
    local groupMargin = math.max(12, math.max(size.X, size.Z) / 2 + 4, math.ceil(maxGroup * (math.max(size.X, size.Z) + 2) / (2 * math.pi)) + 4)
    local width = (columns - 1) * spacing + 2 * groupMargin
    local centerX = (columns - 1) * spacing / 2
    local floorY = -CharacterConfig.RootAnchorOffset
    local trackWidth = 12
    local meleeGap = math.max(16, spacing / 2)
    local meleeTrackZ = -24 - meleeGap
    local maxRange = 0
    for _, row in ipairs(rows) do if row.type == "ranged" then maxRange = math.max(maxRange, row.attackRange) end end
    local rangedTrackZ = meleeTrackZ - meleeGap - groupMargin - maxRange - trackWidth / 2
    local function frame(x: number, z: number): CFrame
        return origin * CFrame.new(x, floorY, z)
    end
    local tracks = {
        {name="MeleeSprintTrack", top=frame(centerX, meleeTrackZ), size=Vector3.new(width, 0, trackWidth)},
        {name="RangedSprintTrack", top=frame(centerX, rangedTrackZ), size=Vector3.new(width, 0, trackWidth)},
    }
    local slots = {}
    for _, row in ipairs(rows) do
        local side = if row.level <= columns then 1 else -1
        local column = (row.level - 1) % columns
        local x = column * spacing
        local ranged = row.type == "ranged"
        local trackZ = if ranged then rangedTrackZ else meleeTrackZ
        local offset = if ranged then trackWidth / 2 + row.attackRange else meleeGap
        local z = trackZ + side * offset
        local approachFrame: CFrame? = nil
        local approachSize: Vector3? = nil
        if ranged then
            approachFrame = frame(x, trackZ + side * (trackWidth / 2 + row.attackRange / 2))
            approachSize = Vector3.new(math.min(10, spacing - 4), 0, row.attackRange)
        end
        local visitDistance = if ranged then row.attackRange * 0.75 else math.min(5, meleeGap - trackWidth / 2 - 1)
        local visit = frame(x, z - side * visitDistance)
        local point = frame(x, z).Position
        local facing = origin.LookVector * side
        slots[row.id] = {point=point, facing=facing, approachFrame=approachFrame, approachSize=approachSize,
            visit=CFrame.lookAt(visit.Position + Vector3.new(0, CharacterConfig.RootAnchorOffset, 0), point + Vector3.new(0, CharacterConfig.RootAnchorOffset, 0))}
    end
    local backEdge = rangedTrackZ - trackWidth / 2 - maxRange - groupMargin
    return {slots=slots, tracks=tracks, platformTop=frame(centerX, (backEdge + groupMargin) / 2), width=width, depth=groupMargin - backEdge}
end
return table.freeze(Layout)
