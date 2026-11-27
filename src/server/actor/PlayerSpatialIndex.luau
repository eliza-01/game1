-- Server-only player candidates for horizontal aggro. One lazy snapshot per
-- synchronous scheduler batch; no extra Heartbeat, parts, or per-player loops.
local Players = game:GetService("Players")
local Root = require(script.Parent:WaitForChild("ActorTargetRoot"))
local Grid = require(script.Parent:WaitForChild("PlayerSpatialGrid"))
local Index = {}
local CELL_SIZE = 32 -- internal tuning, not a gameplay radius
local inBatch = false
local snapshot

local function build()
    local grid = Grid.new(CELL_SIZE)
    for _, player in ipairs(Players:GetPlayers()) do
        local root = Root.Get(player.Character)
        if root then
            local position = root.Position
            grid:Add(player, position.X, position.Z)
        end
    end
    return grid
end

function Index.BeginBatch()
    snapshot = nil
    inBatch = true
end

function Index.EndBatch()
    inBatch = false
    snapshot = nil
end

-- Authoritative character replacement / scripted teleport can occur during
-- a scheduler dispatch. Invalidate before any subsequent acquisition.
function Index.Invalidate()
    snapshot = nil
end

function Index.Query(position, radius)
    local grid = snapshot or build()
    if inBatch then snapshot = grid end
    return grid:Query(position.X, position.Z, radius)
end

Players.PlayerAdded:Connect(Index.Invalidate)
Players.PlayerRemoving:Connect(Index.Invalidate)

return table.freeze(Index)
