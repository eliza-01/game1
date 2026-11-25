--!strict
-- Server-owned floor transfers. Every destination must have an authored
-- house_floor_NN_spawn_socket; elevator bones only expose controls.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local Orientation = require(Shared:WaitForChild("world"):WaitForChild("HouseSpawnOrientation"))
local Policy = require(Shared:WaitForChild("world"):WaitForChild("HouseElevatorPolicy"))
local Floor = require(Shared:WaitForChild("world"):WaitForChild("HouseElevatorFloor"))
local CameraSync = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterCameraSync"))

local Elevator = {}

local function presentFloors(sockets: {[string]: Attachment}): {[number]: boolean}
    local present: {[number]: boolean} = {}
    for floor = 1, 3 do
        local socket = sockets[Policy.SocketName(floor)]
        local spawn = sockets[Policy.DestinationSocket(floor, floor)]
        present[floor] = socket ~= nil and socket.Parent ~= nil and spawn ~= nil and spawn.Parent ~= nil
    end
    return present
end

function Elevator.Options(sockets: {[string]: Attachment}, name: string): {Policy.Option}
    local floor = Policy.Floor(name)
    if not floor or not sockets[name] then return {} end
    return Policy.Options(floor, presentFloors(sockets))
end

function Elevator.Move(player: Player, sockets: {[string]: Attachment}, name: string, key: string): (boolean, string)
    local floor = Policy.Floor(name)
    if not floor or not sockets[name] then return false, "Исходный этаж недоступен" end
    local option = Policy.Resolve(floor, key, presentFloors(sockets))
    if not option then return false, "Это направление лифта недоступно" end
    local target = sockets[Policy.DestinationSocket(floor, option.destination)]
    if not target or not target.Parent then return false, "Целевой этаж недоступен" end
    local character = player.Character
    local root = SpatialRoot.Get(player)
    if not character or not root then return false, "Персонаж не готов" end
    if Floor.FromSockets(root, sockets) ~= floor then
        return false, "Это направление лифта недоступно"
    end
    -- The destination spawn socket owns position and heading on every floor.
    -- The elevator control socket itself is not an orientation frame.
    local targetFrame = Orientation.Upright(if target:IsA("Bone") then target.TransformedWorldCFrame
        else target.WorldCFrame, target:IsA("Bone"), Policy.SpawnClearance)
    if not targetFrame then return false, "Не удалось определить направление персонажа" end
    character:PivotTo(targetFrame)
    local controller = character:FindFirstChildOfClass("ControllerManager")
    if controller then
        controller.MovingDirection = Vector3.zero
        controller.FacingDirection = targetFrame.LookVector
    end
    root.AssemblyLinearVelocity = Vector3.zero
    root.AssemblyAngularVelocity = Vector3.zero
    CameraSync.Align(player, character, targetFrame)
    return true, ("Лифт · этаж %d"):format(option.destination)
end

return table.freeze(Elevator)
