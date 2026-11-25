--!strict
-- Live, house-scoped floor references. No workspace search or player-wide floor cache.
local Policy = require(script.Parent:WaitForChild("HouseElevatorPolicy"))
local Floor = {}
local REFS = "Game1ElevatorFloorReferences"

local function height(socket: Attachment): number
    return (if socket:IsA("Bone") then socket.TransformedWorldCFrame else socket.WorldCFrame).Position.Y
end

function Floor.FromSockets(root: BasePart, sockets: {[string]: Attachment}): number?
    local heights: {[number]: number} = {}
    for floor = 1, 3 do
        local socket = sockets[Policy.DestinationSocket(floor, floor)]
        if socket and socket.Parent then heights[floor] = height(socket) end
    end
    return Policy.CurrentFloor(root.Position.Y, heights, root.Size.Y * 0.5)
end

function Floor.BindPrompt(prompt: ProximityPrompt, sockets: {[string]: Attachment})
    local folder = Instance.new("Folder")
    folder.Name = REFS
    local count = 0
    for floor = 1, 3 do
        local socket = sockets[Policy.DestinationSocket(floor, floor)]
        if socket and socket.Parent then
            local reference = Instance.new("ObjectValue")
            reference.Name = tostring(floor)
            reference.Value = socket
            reference.Parent = folder
            count += 1
        end
    end
    folder:SetAttribute("FloorCount", count)
    folder.Parent = prompt
end

function Floor.FromPrompt(prompt: ProximityPrompt, root: BasePart): number?
    local folder = prompt:FindFirstChild(REFS)
    if not folder then return nil end
    local heights: {[number]: number} = {}
    local count = 0
    for _, reference in folder:GetChildren() do
        if not reference:IsA("ObjectValue") then continue end
        local floor = tonumber(reference.Name)
        local socket = reference.Value
        -- Streaming can temporarily omit a reference: fail closed, then retry
        -- on the next existing prompt update, never guess from the aimed socket.
        if not floor or not socket or not socket:IsA("Attachment") or not socket.Parent then return nil end
        heights[floor] = height(socket)
        count += 1
    end
    if count < 2 or count ~= folder:GetAttribute("FloorCount") then return nil end
    return Policy.CurrentFloor(root.Position.Y, heights, root.Size.Y * 0.5)
end

function Floor.AllowsPrompt(prompt: ProximityPrompt, root: BasePart): boolean
    local source = Policy.Floor(tostring(prompt:GetAttribute("Game1HouseSocketName")))
    return source == nil or Floor.FromPrompt(prompt, root) == source
end

return table.freeze(Floor)
