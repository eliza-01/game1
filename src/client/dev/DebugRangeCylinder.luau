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
-- A single Roblox Cylinder Part is one-sided from inside. The local inner wall
-- uses flat double-sided BasePart faces, so the perimeter remains visible from
-- either side without camera-dependent overlays or replicated instances.
local INNER_WALL_SEGMENTS = 64
local WALL_THICKNESS = 0.12
local WALL_TRANSPARENCY = 0.6

local function updateWallGeometry(cylinder: Part, wall: {BasePart}, radius: number)
    if #wall == 0 then return end
    local halfAngle = math.pi / INNER_WALL_SEGMENTS
    local inradius = math.max(0.3, radius * math.cos(halfAngle) - 0.15)
    local width = 2 * inradius * math.tan(halfAngle) + 0.05
    for index, panel in ipairs(wall) do
        local angle = (index - 0.5) * math.pi * 2 / INNER_WALL_SEGMENTS
        local radialY, radialZ = math.cos(angle), math.sin(angle)
        local tangent = Vector3.new(0, -radialZ, radialY)
        local offset = Vector3.new(0, inradius * radialY, inradius * radialZ)
        panel.Size = Vector3.new(HEIGHT, width, WALL_THICKNESS)
        panel.CFrame = cylinder.CFrame * CFrame.fromMatrix(offset, Vector3.xAxis, tangent)
    end
end

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
    local model = Instance.new("Model")
    model.Name = "Game1TestRangePreview"
    cylinder.Parent = model
    model.PrimaryPart = cylinder
    return setmetatable({
        _model = model, _part = cylinder, _walls = {}, _range = 50,
        _visible = false, _hasRoot = nil, _connection = nil,
    }, DebugRangeCylinder)
end

function DebugRangeCylinder:_ensureInnerWall()
    if #self._walls > 0 then return end
    for index = 1, INNER_WALL_SEGMENTS do
        local panel = Instance.new("Part")
        panel.Name = "InnerWall_" .. index
        panel.Material = Enum.Material.Neon
        panel.Color = self._part.Color
        panel.Transparency = WALL_TRANSPARENCY
        panel.Anchored = true
        panel.CanCollide = false
        panel.CanTouch = false
        panel.CanQuery = false
        panel.CastShadow = false
        panel.Locked = true
        panel.Parent = self._model
        table.insert(self._walls, panel)
    end
    updateWallGeometry(self._part, self._walls, self._range)
end

function DebugRangeCylinder:_setRendered(hasRoot: boolean)
    if self._hasRoot == hasRoot then return end
    self._hasRoot = hasRoot
    local alpha = if hasRoot then WALL_TRANSPARENCY else 1
    self._part.Transparency = alpha
    for _, panel in self._walls do
        panel.Transparency = alpha
    end
end

function DebugRangeCylinder:SetRange(value: number): number
    if value ~= value or value == math.huge or value == -math.huge then
        return self._range
    end
    self._range = math.clamp(math.round(value * 100) / 100, MIN_RANGE, MAX_RANGE)
    self._part.Size = Vector3.new(HEIGHT, 2 * self._range, 2 * self._range)
    updateWallGeometry(self._part, self._walls, self._range)
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
        -- One model pivot per render step, not 64 individual wall updates.
        self._model:PivotTo(CFrame.new(root.Position) * CFrame.Angles(0, 0, math.rad(90)))
        self:_setRendered(true)
    else
        self:_setRendered(false)
    end
end

function DebugRangeCylinder:SetVisible(value: boolean)
    local visible = value == true
    if visible == self._visible then return end
    self._visible = visible
    if visible then
        self:_ensureInnerWall()
        self:SetRange(self._range)
        self._model.Parent = Workspace
        self:_update()
        self._connection = RunService.RenderStepped:Connect(function()
            self:_update()
        end)
    else
        if self._connection then self._connection:Disconnect() self._connection = nil end
        self._model.Parent = nil
        self._hasRoot = nil
    end
end

function DebugRangeCylinder:Destroy()
    self:SetVisible(false)
    self._model:Destroy()
end

return DebugRangeCylinder
