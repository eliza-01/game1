--!strict
-- Server-owned floor transfers. Only real registered authored floor spawns
-- may be destinations on floors 1 and 2; elevator Bones are the controls.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local Orientation = require(Shared:WaitForChild("world"):WaitForChild("HouseSpawnOrientation"))
local Policy = require(Shared:WaitForChild("world"):WaitForChild("HouseElevatorPolicy"))

local Elevator = {}

local function presentFloors(sockets: {[string]: Attachment}): {[number]: boolean}
    local present: {[number]: boolean} = {}
    for floor = 1, 3 do
        local socket = sockets[Policy.SocketName(floor)]
        present[floor] = socket ~= nil and socket.Parent ~= nil
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
    -- Preserve the player's heading; elevator authoring bones are positions,
    -- not avatar orientation frames. Reuse the shared upright conversion.
    local point = if target:IsA("Bone") then target.TransformedWorldCFrame.Position else target.WorldPosition
    local targetFrame: CFrame?
    if option.destination == 1 or option.destination == 2 then
        -- Both floor spawns encode Blender Tail -> Head; match Studio TP.
        targetFrame = Orientation.Upright(if target:IsA("Bone") then target.TransformedWorldCFrame
            else target.WorldCFrame, target:IsA("Bone"), 3)
    else
        targetFrame = Orientation.Upright(CFrame.new(point) * root.CFrame.Rotation, false, 3)
    end
    if not targetFrame then return false, "Не удалось определить направление персонажа" end
    character:PivotTo(targetFrame)
    local controller = character:FindFirstChildOfClass("ControllerManager")
    if controller then
        controller.MovingDirection = Vector3.zero
        controller.FacingDirection = targetFrame.LookVector
    end
    root.AssemblyLinearVelocity = Vector3.zero
    root.AssemblyAngularVelocity = Vector3.zero
    return true, ("Лифт · этаж %d"):format(option.destination)
end

return table.freeze(Elevator)
