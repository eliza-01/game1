--!strict
-- Canonical authored socket direction across the game.
-- Blender Bone local +Y points HEAD -> TAIL; the visible item's FRONT
-- points TAIL -> HEAD, therefore Roblox Bone -UpVector is forward.
-- An Attachment is a regular Roblox socket: local -Z / LookVector is front.
-- Bone local -Z defines the secondary UP axis (roll) for rigid items.
-- Positional and upright-only consumers may use Forward without FullFrame.
local SocketFacing = {}

function SocketFacing.Forward(frame: CFrame, fromBone: boolean): Vector3
    return if fromBone then -frame.UpVector else frame.LookVector
end

function SocketFacing.FullFrame(frame: CFrame, fromBone: boolean): CFrame
    if not fromBone then return frame end
    -- The two axes belong to the *same* animated Bone frame. This preserves
    -- its authored roll and head movement without individual 90-degree hacks.
    return CFrame.lookAlong(frame.Position, SocketFacing.Forward(frame, true), frame.LookVector)
end

return table.freeze(SocketFacing)
