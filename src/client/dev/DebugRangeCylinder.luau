-- Studio-only world-range visualization. One client-local cylinder follows the
-- current avatar; it never participates in collisions, combat or replication.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local DebugRangeCylinder = {}
DebugRangeCylinder.__index = DebugRangeCylinder

local HEIGHT = 200
local MIN_RANGE = 1
local MAX_RANGE = 1000

function DebugRangeCylinder.new(): any
    local cylinder = Instance.new("Part")
    cylinder.Name = "Game1TestRangeCylinder"
    cylinder.Shape = Enum.PartType.Cylinder
    cylinder.Material = Enum.Material.SmoothPlastic
    cylinder.Color = Color3.fromRGB(72, 214, 180)
    cylinder.Transparency = 0.6
    cylinder.Anchored = true
    cylinder.CanCollide = false
    cylinder.CanTouch = false
    cylinder.CanQuery = false
    cylinder.CastShadow = false
    cylinder.Locked = true
    return setmetatable({ _part = cylinder, _range = 50, _visible = false, _connection = nil }, DebugRangeCylinder)
end

function DebugRangeCylinder:SetRange(value: number): number
    if value ~= value or value == math.huge or value == -math.huge then
        return self._range
    end
    self._range = math.clamp(math.round(value * 100) / 100, MIN_RANGE, MAX_RANGE)
    self._part.Size = Vector3.new(HEIGHT, 2 * self._range, 2 * self._range)
    return self._range
end

function DebugRangeCylinder:GetRange(): number
    return self._range
end

function DebugRangeCylinder:_update()
    local character = Players.LocalPlayer.Character
    local root = character and (character:FindFirstChild("RootCollider") or character:FindFirstChild("HumanoidRootPart"))
    if root and root:IsA("BasePart") then
        -- Cylinder's long axis is X in Roblox. Rotate it into the world Y axis.
        self._part.CFrame = CFrame.new(root.Position) * CFrame.Angles(0, 0, math.rad(90))
        self._part.Transparency = 0.6
    else
        self._part.Transparency = 1
    end
end

function DebugRangeCylinder:SetVisible(value: boolean)
    local visible = value == true
    if visible == self._visible then return end
    self._visible = visible
    if visible then
        self:SetRange(self._range)
        self._part.Parent = Workspace
        self:_update()
        self._connection = RunService.RenderStepped:Connect(function()
            self:_update()
        end)
    else
        if self._connection then self._connection:Disconnect() self._connection = nil end
        self._part.Parent = nil
    end
end

function DebugRangeCylinder:Destroy()
    self:SetVisible(false)
    self._part:Destroy()
end

return DebugRangeCylinder
