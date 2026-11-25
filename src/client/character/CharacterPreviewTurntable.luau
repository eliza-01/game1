--!strict
-- Local presentation only: horizontal drag in the free scene, not the camera.
local UserInputService = game:GetService("UserInputService")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local Mounts = require(script.Parent:WaitForChild("BoneMountedAttachmentController"))

local Turntable = {}
Turntable.__index = Turntable
local SENSITIVITY = math.rad(0.35)
local RESPONSE = 12
local MAX_SPEED = math.rad(150)
local MAX_PENDING = math.rad(35)

type Rotation = {base: CFrame, angle: number, target: number}

-- Preview meshes intentionally have CanQuery=false. Intersect their oriented
-- visual bounds without enabling world raycasts or adding invisible hitboxes.
function Turntable.HitDistance(part: BasePart, ray: Ray): number?
    local origin = part.CFrame:PointToObjectSpace(ray.Origin)
    local direction = part.CFrame:VectorToObjectSpace(ray.Direction)
    local half = part.Size * 0.5
    local near, far = 0, math.huge
    for _, axis in ipairs({{origin.X, direction.X, half.X}, {origin.Y, direction.Y, half.Y},
        {origin.Z, direction.Z, half.Z}}) do
        local o, d, h = axis[1], axis[2], axis[3]
        if math.abs(d) < 1e-7 then
            if math.abs(o) > h then return nil end
        else
            local a, b = (-h - o) / d, (h - o) / d
            near = math.max(near, math.min(a, b))
            far = math.min(far, math.max(a, b))
            if near > far then return nil end
        end
    end
    return near
end

function Turntable.Advance(angle: number, target: number, dt: number): number
    local errorAngle = target - angle
    local step = math.clamp(errorAngle * (1 - math.exp(-RESPONSE * dt)), -MAX_SPEED * dt, MAX_SPEED * dt)
    return if math.abs(errorAngle) < 0.0001 then target else angle + step
end

local function pose(base: CFrame, angle: number): CFrame
    return CFrame.new(base.Position) * CFrame.Angles(0, angle, 0) * base.Rotation
end

local function pick(models: {[string]: Model}, position: Vector2): string?
    local camera = Workspace.CurrentCamera
    if not camera then return nil end
    -- InputObject.Position and GetMouseLocation are viewport coordinates.
    local ray = camera:ViewportPointToRay(position.X, position.Y)
    local closest = math.huge
    local result: string? = nil
    for id, model in pairs(models) do
        if not model.Parent then continue end
        for _, part in ipairs(model:GetDescendants()) do
            if part:IsA("MeshPart") and part.Transparency < 0.99 and part.LocalTransparencyModifier < 0.99 then
                local distance = Turntable.HitDistance(part, ray)
                if distance and distance < closest then closest, result = distance, id end
            end
        end
    end
    return result
end

-- In the overview, a drag outside both models controls the closest visible
-- podium by screen position. A selected avatar always takes precedence.
function Turntable.Target(models: {[string]: Model}, position: Vector2, selected: string?, freeScene: boolean): string?
    if freeScene and selected then
        local model = models[selected]
        return if model and model.Parent then selected else nil
    end
    local id = pick(models, position)
    if id or not freeScene then return id end
    local camera = Workspace.CurrentCamera
    if not camera then return nil end
    local best = math.huge
    for key, model in pairs(models) do
        if model.Parent then
            local point = camera:WorldToViewportPoint(model:GetPivot().Position)
            if point.Z > 0 then
                local distance = (Vector2.new(point.X, point.Y) - position).Magnitude
                if distance < best then best, id = distance, key end
            end
        end
    end
    return id
end

function Turntable.new(models: {[string]: Model}, enabled: () -> boolean, freeTarget: (() -> (string?, boolean))?)
    local self = setmetatable({models = models, enabled = enabled, rotations = {} :: {[string]: Rotation},
        connections = {} :: {RBXScriptConnection}, drag = nil :: InputObject?, dragId = nil :: string?, lastX = 0}, Turntable)
    local function connect(signal: RBXScriptSignal, callback: any)
        table.insert(self.connections, signal:Connect(callback))
    end
    connect(UserInputService.InputBegan, function(input: InputObject, processed: boolean)
        if self.drag or not enabled() or processed then return end
        local kind = input.UserInputType
        if kind ~= Enum.UserInputType.MouseButton1 and kind ~= Enum.UserInputType.Touch then return end
        if UserInputService:GetFocusedTextBox() or UiInputGuard.IsPointerOverUi(input) then return end
        local position = Vector2.new(input.Position.X, input.Position.Y)
        local selected: string? = nil
        local freeScene = false
        if freeTarget then selected, freeScene = freeTarget() end
        local id = Turntable.Target(models, position, selected, freeScene)
        if not id or not self.rotations[id] then return end
        self.drag, self.dragId, self.lastX = input, id, position.X
    end)
    connect(UserInputService.InputChanged, function(input: InputObject)
        local drag = self.drag
        if not drag then return end
        if not enabled() then self:Cancel(); return end
        if drag.UserInputType == Enum.UserInputType.Touch then
            if input ~= drag then return end
        elseif input.UserInputType ~= Enum.UserInputType.MouseMovement then return end
        local id = self.dragId
        local rotation = id and self.rotations[id]
        if not rotation then self:Cancel(); return end
        local delta = input.Position.X - self.lastX
        self.lastX = input.Position.X
        rotation.target = rotation.angle + math.clamp(rotation.target - rotation.angle + delta * SENSITIVITY,
            -MAX_PENDING, MAX_PENDING)
    end)
    connect(UserInputService.InputEnded, function(input: InputObject)
        local drag = self.drag
        if drag and (input == drag or (drag.UserInputType == Enum.UserInputType.MouseButton1
            and input.UserInputType == Enum.UserInputType.MouseButton1)) then self:Cancel() end
    end)
    connect(UserInputService.WindowFocusReleased, function() self:Cancel() end)
    connect(RunService.RenderStepped, function(dt: number)
        if not enabled() then
            self:Cancel()
            for _, rotation in pairs(self.rotations) do rotation.target = rotation.angle end
            return
        end
        if self.drag and (self.drag.UserInputState == Enum.UserInputState.Cancel
            or self.drag.UserInputState == Enum.UserInputState.End) then self:Cancel() end
        for id, rotation in pairs(self.rotations) do
            local model = models[id]
            if model and model.Parent and rotation.angle ~= rotation.target then
                rotation.angle = Turntable.Advance(rotation.angle, rotation.target, dt)
                model:PivotTo(pose(rotation.base, rotation.angle))
                Mounts.UpdateCharacter(model)
            end
        end
    end)
    return self
end

function Turntable:Cancel()
    self.drag, self.dragId = nil, nil
end

-- Reapply the current angle at the atomic replacement boundary, not at the
-- beginning of an asynchronous build: the old model may have rotated meanwhile.
function Turntable:Place(id: string, model: Model, base: CFrame)
    local rotation = self.rotations[id]
    if not rotation then
        rotation = {base = base, angle = 0, target = 0}
        self.rotations[id] = rotation
    end
    rotation.base = base
    model:PivotTo(pose(base, rotation.angle))
end

function Turntable:Remove(id: string)
    if self.dragId == id then self:Cancel() end
    self.rotations[id] = nil
end

function Turntable:Destroy()
    self:Cancel()
    for _, connection in ipairs(self.connections) do connection:Disconnect() end
    table.clear(self.connections)
    table.clear(self.rotations)
end

return Turntable
