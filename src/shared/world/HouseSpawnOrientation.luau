--!strict
-- Interpret authoring socket axes at the character-spawn boundary.
-- Blender Bone: -Y (Tail -> Head) is authored spawn forward. Imported Roblox
-- Bone +Y (Head -> Tail) is UpVector, so forward is -UpVector.
-- Ordinary Roblox Attachments follow the normal -Z / LookVector convention.
-- Characters always stand along the WORLD Y axis, independent of bone roll.
local Orientation = {}
local WORLD_UP = Vector3.yAxis
local MIN_FORWARD_LENGTH = 1e-4

function Orientation.Upright(socketFrame: CFrame, fromBone: boolean, clearance: number): CFrame?
    local authoredForward = if fromBone then -socketFrame.UpVector else socketFrame.LookVector
    local horizontalForward = Vector3.new(authoredForward.X, 0, authoredForward.Z)
    local magnitude = horizontalForward.Magnitude
    if magnitude < MIN_FORWARD_LENGTH then
        -- A vertical bone axis has no meaningful facing on the floor.
        -- Reject it rather than silently choosing an unrelated world heading.
        return nil
    end
    local position = socketFrame.Position + WORLD_UP * clearance
    return CFrame.lookAlong(position, horizontalForward / magnitude, WORLD_UP)
end

return table.freeze(Orientation)
